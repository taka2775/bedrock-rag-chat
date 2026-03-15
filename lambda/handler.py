import json
import os

import boto3

bedrock_agent_runtime = boto3.client("bedrock-agent-runtime")

KNOWLEDGE_BASE_ID = os.environ["KNOWLEDGE_BASE_ID"]
ACCOUNT_ID = boto3.client("sts").get_caller_identity()["Account"]
REGION = os.environ.get("AWS_REGION", "us-east-1")
MODEL_ARN = os.environ.get(
    "MODEL_ARN",
    f"arn:aws:bedrock:{REGION}:{ACCOUNT_ID}:inference-profile/us.anthropic.claude-sonnet-4-20250514-v1:0",
)


def handler(event, context):
    body = json.loads(event.get("body", "{}"))
    query = body.get("query", "")

    if not query:
        return {
            "statusCode": 400,
            "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": "query is required"}),
        }

    response = bedrock_agent_runtime.retrieve_and_generate(
        input={"text": query},
        retrieveAndGenerateConfiguration={
            "type": "KNOWLEDGE_BASE",
            "knowledgeBaseConfiguration": {
                "knowledgeBaseId": KNOWLEDGE_BASE_ID,
                "modelArn": MODEL_ARN,
            },
        },
    )

    output = response["output"]["text"]
    citations = []
    for citation in response.get("citations", []):
        for ref in citation.get("retrievedReferences", []):
            citations.append({
                "text": ref.get("content", {}).get("text", ""),
                "source": ref.get("location", {}).get("s3Location", {}).get("uri", ""),
            })

    return {
        "statusCode": 200,
        "headers": {"Content-Type": "application/json", "Access-Control-Allow-Origin": "*"},
        "body": json.dumps({
            "answer": output,
            "citations": citations,
        }, ensure_ascii=False),
    }
