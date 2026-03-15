import aws_cdk as cdk
from stacks.knowledge_base_stack import KnowledgeBaseStack
from stacks.api_stack import ApiStack

app = cdk.App()

kb_stack = KnowledgeBaseStack(app, "KnowledgeBaseStack",
    env=cdk.Environment(region="us-east-1"),
)

api_stack = ApiStack(app, "ApiStack",
    knowledge_base_id=kb_stack.knowledge_base.attr_knowledge_base_id,
    env=cdk.Environment(region="us-east-1"),
)

app.synth()
