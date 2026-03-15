import aws_cdk as cdk
from stacks.knowledge_base_stack import KnowledgeBaseStack

app = cdk.App()

kb_stack = KnowledgeBaseStack(app, "KnowledgeBaseStack",
    env=cdk.Environment(region="us-east-1"),
)

app.synth()
