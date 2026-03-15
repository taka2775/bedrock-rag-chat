from aws_cdk import (
    Stack,
    Duration,
    aws_lambda as _lambda,
    aws_apigateway as apigw,
    aws_iam as iam,
)
from constructs import Construct


class ApiStack(Stack):
    def __init__(self, scope: Construct, id: str, knowledge_base_id: str, **kwargs):
        super().__init__(scope, id, **kwargs)

        chat_fn = _lambda.Function(
            self, "ChatFunction",
            runtime=_lambda.Runtime.PYTHON_3_12,
            handler="handler.handler",
            code=_lambda.Code.from_asset("../lambda"),
            timeout=Duration.seconds(30),
            memory_size=256,
            environment={
                "KNOWLEDGE_BASE_ID": knowledge_base_id,
            },
        )

        chat_fn.add_to_role_policy(
            iam.PolicyStatement(
                actions=[
                    "bedrock:RetrieveAndGenerate",
                    "bedrock:Retrieve",
                    "bedrock:InvokeModel",
                    "bedrock:GetInferenceProfile",
                ],
                resources=["*"],
            )
        )

        api = apigw.RestApi(
            self, "ChatApi",
            rest_api_name="Bedrock RAG Chat API",
            default_cors_preflight_options=apigw.CorsOptions(
                allow_origins=apigw.Cors.ALL_ORIGINS,
                allow_methods=["POST", "OPTIONS"],
            ),
        )

        chat_resource = api.root.add_resource("chat")
        chat_resource.add_method(
            "POST",
            apigw.LambdaIntegration(chat_fn),
        )
