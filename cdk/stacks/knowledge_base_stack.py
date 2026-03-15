import json

from aws_cdk import (
    Stack,
    RemovalPolicy,
    CfnOutput,
    aws_s3 as s3,
    aws_opensearchserverless as aoss,
    aws_bedrock as bedrock,
    aws_iam as iam,
)
from constructs import Construct


class KnowledgeBaseStack(Stack):
    def __init__(self, scope: Construct, id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        # S3 バケット
        self.doc_bucket = s3.Bucket(
            self, "DocBucket",
            bucket_name=f"bedrock-rag-docs-{self.account}",
            removal_policy=RemovalPolicy.DESTROY,
            auto_delete_objects=True,
        )

        # Bedrock Knowledge Base 用 IAM ロール
        self.kb_role = iam.Role(
            self, "KBRole",
            assumed_by=iam.ServicePrincipal("bedrock.amazonaws.com"),
            inline_policies={
                "BedrockKBPolicy": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock:InvokeModel"],
                            resources=["*"],
                        ),
                        iam.PolicyStatement(
                            actions=["s3:GetObject", "s3:ListBucket"],
                            resources=[
                                self.doc_bucket.bucket_arn,
                                f"{self.doc_bucket.bucket_arn}/*",
                            ],
                        ),
                        iam.PolicyStatement(
                            actions=["aoss:APIAccessAll"],
                            resources=["*"],
                        ),
                    ]
                )
            },
        )

        # OpenSearch Serverless
        collection_name = "bedrock-rag-vectors"

        encryption_policy = aoss.CfnSecurityPolicy(
            self, "EncryptionPolicy",
            name=f"{collection_name}-enc",
            type="encryption",
            policy=json.dumps({
                "Rules": [
                    {
                        "ResourceType": "collection",
                        "Resource": [f"collection/{collection_name}"],
                    }
                ],
                "AWSOwnedKey": True,
            }),
        )

        network_policy = aoss.CfnSecurityPolicy(
            self, "NetworkPolicy",
            name=f"{collection_name}-net",
            type="network",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                        },
                        {
                            "ResourceType": "dashboard",
                            "Resource": [f"collection/{collection_name}"],
                        },
                    ],
                    "AllowFromPublic": True,
                }
            ]),
        )

        self.collection = aoss.CfnCollection(
            self, "VectorCollection",
            name=collection_name,
            type="VECTORSEARCH",
        )
        self.collection.add_dependency(encryption_policy)
        self.collection.add_dependency(network_policy)

        data_access_policy = aoss.CfnAccessPolicy(
            self, "DataAccessPolicy",
            name=f"{collection_name}-access",
            type="data",
            policy=json.dumps([
                {
                    "Rules": [
                        {
                            "ResourceType": "collection",
                            "Resource": [f"collection/{collection_name}"],
                            "Permission": [
                                "aoss:CreateCollectionItems",
                                "aoss:UpdateCollectionItems",
                                "aoss:DescribeCollectionItems",
                            ],
                        },
                        {
                            "ResourceType": "index",
                            "Resource": [f"index/{collection_name}/*"],
                            "Permission": [
                                "aoss:CreateIndex",
                                "aoss:DeleteIndex",
                                "aoss:UpdateIndex",
                                "aoss:DescribeIndex",
                                "aoss:ReadDocument",
                                "aoss:WriteDocument",
                            ],
                        },
                    ],
                    "Principal": [
                        self.kb_role.role_arn,
                        f"arn:aws:iam::{self.account}:role/cdk-hnb659fds-cfn-exec-role-{self.account}-{self.region}",
                    ],
                }
            ]),
        )

        # ベクトルインデックス
        index_name = "bedrock-rag-index"

        vector_index = aoss.CfnIndex(
            self, "VectorIndex",
            collection_endpoint=self.collection.attr_collection_endpoint,
            index_name=index_name,
            settings={
                "index": {
                    "knn": True,
                },
            },
            mappings={
                "properties": {
                    "bedrock-knowledge-base-default-vector": {
                        "type": "knn_vector",
                        "dimension": 1024,
                        "method": {
                            "engine": "faiss",
                            "name": "hnsw",
                        },
                    },
                    "AMAZON_BEDROCK_TEXT_CHUNK": {
                        "type": "text",
                    },
                    "AMAZON_BEDROCK_METADATA": {
                        "type": "text",
                        "index": False,
                    },
                },
            },
        )
        vector_index.add_dependency(data_access_policy)

        # Bedrock Knowledge Base
        embedding_model_arn = f"arn:aws:bedrock:{self.region}::foundation-model/amazon.titan-embed-text-v2:0"

        self.knowledge_base = bedrock.CfnKnowledgeBase(
            self, "KnowledgeBase",
            name="bedrock-rag-kb",
            role_arn=self.kb_role.role_arn,
            knowledge_base_configuration=bedrock.CfnKnowledgeBase.KnowledgeBaseConfigurationProperty(
                type="VECTOR",
                vector_knowledge_base_configuration=bedrock.CfnKnowledgeBase.VectorKnowledgeBaseConfigurationProperty(
                    embedding_model_arn=embedding_model_arn,
                ),
            ),
            storage_configuration=bedrock.CfnKnowledgeBase.StorageConfigurationProperty(
                type="OPENSEARCH_SERVERLESS",
                opensearch_serverless_configuration=bedrock.CfnKnowledgeBase.OpenSearchServerlessConfigurationProperty(
                    collection_arn=self.collection.attr_arn,
                    vector_index_name=index_name,
                    field_mapping=bedrock.CfnKnowledgeBase.OpenSearchServerlessFieldMappingProperty(
                        vector_field="bedrock-knowledge-base-default-vector",
                        text_field="AMAZON_BEDROCK_TEXT_CHUNK",
                        metadata_field="AMAZON_BEDROCK_METADATA",
                    ),
                ),
            ),
        )
        self.knowledge_base.add_dependency(vector_index)

        # データソース（S3 と Knowledge Base の紐付け）
        bedrock.CfnDataSource(
            self, "S3DataSource",
            name="rag-docs",
            knowledge_base_id=self.knowledge_base.attr_knowledge_base_id,
            data_source_configuration=bedrock.CfnDataSource.DataSourceConfigurationProperty(
                type="S3",
                s3_configuration=bedrock.CfnDataSource.S3DataSourceConfigurationProperty(
                    bucket_arn=self.doc_bucket.bucket_arn,
                ),
            ),
            vector_ingestion_configuration=bedrock.CfnDataSource.VectorIngestionConfigurationProperty(
                chunking_configuration=bedrock.CfnDataSource.ChunkingConfigurationProperty(
                    chunking_strategy="FIXED_SIZE",
                    fixed_size_chunking_configuration=bedrock.CfnDataSource.FixedSizeChunkingConfigurationProperty(
                        max_tokens=300,
                        overlap_percentage=20,
                    ),
                ),
            ),
        )

        CfnOutput(self, "KnowledgeBaseId", value=self.knowledge_base.attr_knowledge_base_id)