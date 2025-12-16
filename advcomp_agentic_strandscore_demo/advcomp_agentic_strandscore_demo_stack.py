import logging
from aws_cdk import (
    Stack,
    RemovalPolicy,
    Duration,
    CfnOutput,
    aws_iam as iam,
    aws_s3 as s3,
    aws_lambda as aws_lambda,
    aws_ecr as ecr,
    aws_ecr_assets as ecr_assets,
    aws_bedrockagentcore as agentcore,
    aws_cognito as cognito,
)
from aws_cdk import aws_bedrock_agentcore_alpha as agentcore_alpha
from constructs import Construct
import cdk_ecr_deployment as ecr_deploy
from cdklabs.generative_ai_cdk_constructs import bedrock

# Configure logging
logger = logging.getLogger(__name__)

class AdvcompAgenticStrandscoreDemoStack(Stack):
    """
    CDK stack for Advanced Computing Team Collaboration Swarm infrastructure.
    
    This stack creates:
    1. S3 buckets for domain knowledge bases
    2. IAM roles for AgentCore Runtime, Gateway, and Lambda
    3. AgentCore Gateway with IAM authentication
    4. AgentCore Runtime with agent container
    5. Lambda function for knowledge base queries
    6. ECR repository for agent images
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # Create S3 buckets for domain-specific knowledge bases
        # Use account ID as part of the bucket name for uniqueness but consistency
        account_id = self.account
        region_name = self.region
        
        # Use account ID for global uniqueness across AWS accounts
        suffix = account_id  # Use account ID to ensure unique bucket names
        
        # Create S3 buckets for each domain
        domain_buckets = {}
        domains = ["hpc", "quantum", "genai", "visual", "spatial", "iot", "partners"]
        
        for domain in domains:
            # Create bucket with account ID for global uniqueness
            bucket_name = f"advcomp-{domain}-kb-{suffix}"
            bucket = s3.Bucket(
                self, f"{domain.capitalize()}KnowledgeBucket",
                bucket_name=bucket_name,
                removal_policy=RemovalPolicy.DESTROY,
                auto_delete_objects=True
            )
            domain_buckets[domain] = bucket
        
        # We don't need a general knowledge bucket, as we have domain-specific buckets
        
        # Create a new agent role with account ID for uniqueness
        agent_role = iam.Role(
            self, "AgentSwarmRole",
            role_name=f"AdvCompSwarmAgentRole-{account_id}",
            assumed_by=iam.CompositePrincipal(
                iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                iam.ServicePrincipal("bedrock.amazonaws.com")
            ),
            inline_policies={
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "bedrock:InvokeModel",
                                "bedrock:InvokeModelWithResponseStream"
                            ],
                            resources=["*"]
                        ),

                    ]
                ),
                "CloudWatchLogs": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Apply removal policy to the underlying CloudFormation resource
        cfn_agent_role = agent_role.node.default_child
        cfn_agent_role.apply_removal_policy(RemovalPolicy.DESTROY)  # Delete role when stack is destroyed
        
        # Add custom policy for ECR access
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "ecr:GetAuthorizationToken",
                "ecr:BatchGetImage",
                "ecr:GetDownloadUrlForLayer"
            ],
            resources=["*"]
        ))
        
        # Add AgentCore Memory permissions
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock-agentcore:ListMemories",
                "bedrock-agentcore:CreateMemory",
                "bedrock-agentcore:GetMemory",
                "bedrock-agentcore:CreateEvent",
                "bedrock-agentcore:GetEvent",
                "bedrock-agentcore:ListEvents",
                "bedrock-agentcore:ListMemoryRecords",
                "bedrock-agentcore:GetMemoryRecord",
                "bedrock-agentcore:RetrieveMemoryRecords",
                "bedrock-agentcore:DeleteMemoryRecord",
                "bedrock-agentcore:ListActors"
            ],
            resources=["*"]
        ))
        
        # Add specific Bedrock model invocation permissions
        agent_role.add_to_policy(iam.PolicyStatement(
            actions=[
                "bedrock:InvokeModel",
                "bedrock:InvokeModelWithResponseStream"
            ],
            resources=["*"]
        ))
        
        # Import existing Lambda role if it exists, otherwise create a new one
        try:
            lambda_role = iam.Role.from_role_name(
                self, "ImportedLambdaRole",
                role_name="KnowledgeBaseLambdaRole"
            )
            # If we get here, the role exists
            self.lambda_role_exists = True
        except:
            # Create a new role with account ID for uniqueness
            lambda_role = iam.Role(
                self, "LambdaRoleNew",
                role_name=f"KnowledgeBaseLambdaRole-{account_id}",
                assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
                inline_policies={
                    "BedrockKnowledgeBase": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                actions=["bedrock:Retrieve"],
                                resources=["*"]
                            )
                        ]
                    ),
                    "CloudWatchLogs": iam.PolicyDocument(
                        statements=[
                            iam.PolicyStatement(
                                actions=[
                                    "logs:CreateLogGroup",
                                    "logs:CreateLogStream",
                                    "logs:PutLogEvents"
                                ],
                                resources=["*"]
                            )
                        ]
                    )
                }
            )
            
            # Add specific Bedrock Knowledge Base permissions
            lambda_role.add_to_policy(iam.PolicyStatement(
                actions=[
                    "bedrock:Retrieve",
                    "bedrock:RetrieveAndGenerate",
                    "bedrock:InvokeModel",
                    "bedrock:GetInferenceProfile"
                ],
                resources=["*"]
            ))
            
            # Apply removal policy to the underlying CloudFormation resource
            cfn_lambda_role = lambda_role.node.default_child
            cfn_lambda_role.apply_removal_policy(RemovalPolicy.DESTROY)  # Delete role when stack is destroyed
            self.lambda_role_exists = False
        
        # Add Lambda function
        # Use account ID for Lambda function name
        self.lambda_function = aws_lambda.Function(
            self, "KnowledgeBaseFunction",
            function_name=f"advcomp-knowledge-base-{account_id}",
            runtime=aws_lambda.Runtime.PYTHON_3_10,
            handler="knowledge_base_lambda.lambda_handler",
            code=aws_lambda.Code.from_asset("gateway_tools/knowledge_base"),
            role=lambda_role,
            timeout=Duration.seconds(60),  # Increase timeout for real knowledge base queries
            memory_size=256,  # Increase memory for real knowledge base queries
            description="Knowledge base access for Advanced Computing Team Collaboration Swarm",
            environment={
                # Pass knowledge base IDs as environment variables
                # These will be populated after the knowledge bases are created
            }
        )
        
        # Apply removal policy to the underlying CloudFormation resource
        cfn_lambda = self.lambda_function.node.default_child
        cfn_lambda.apply_removal_policy(RemovalPolicy.DESTROY)  # Delete function when stack is destroyed
        
        # Create a new MCP role with account ID for uniqueness
        mcp_role = iam.Role(
            self, "MCPServerRole",
            role_name=f"AdvCompMCPServerRole-{account_id}",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
            inline_policies={
                "BedrockAccess": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["bedrock:InvokeModel"],
                            resources=["*"]
                        )
                    ]
                ),
                "LambdaInvoke": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=["lambda:InvokeFunction"],
                            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:advcomp-knowledge-base-*"]
                        )
                    ]
                ),
                "CloudWatchLogs": iam.PolicyDocument(
                    statements=[
                        iam.PolicyStatement(
                            actions=[
                                "logs:CreateLogGroup",
                                "logs:CreateLogStream",
                                "logs:PutLogEvents"
                            ],
                            resources=["*"]
                        )
                    ]
                )
            }
        )
        
        # Apply removal policy to the underlying CloudFormation resource
        cfn_mcp_role = mcp_role.node.default_child
        cfn_mcp_role.apply_removal_policy(RemovalPolicy.DESTROY)  # Delete role when stack is destroyed
        
        # Add policies for MCP server only if we created a new role
        if not hasattr(self, 'mcp_role_exists') or not self.mcp_role_exists:
            if hasattr(mcp_role, 'add_to_policy'):
                # Add ECR permissions
                mcp_role.add_to_policy(iam.PolicyStatement(
                    actions=[
                        "ecr:GetAuthorizationToken",
                        "ecr:BatchGetImage",
                        "ecr:GetDownloadUrlForLayer"
                    ],
                    resources=["*"]
                ))
                
                # Add Lambda invoke permissions
                mcp_role.add_to_policy(iam.PolicyStatement(
                    actions=["lambda:InvokeFunction"],
                    resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:advcomp-knowledge-base-*"]
                ))
        
        # Create a new gateway role with account ID for uniqueness
        gateway_role = iam.Role(
            self, "GatewayRole",
            role_name=f"AdvCompGatewayRole-{account_id}",
            assumed_by=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com")
        )
        
        # Apply removal policy to the underlying CloudFormation resource
        cfn_gateway_role = gateway_role.node.default_child
        cfn_gateway_role.apply_removal_policy(RemovalPolicy.DESTROY)  # Delete role when stack is destroyed
        
        # Add Lambda invoke permissions with wildcard to handle suffix
        lambda_invoke_policy = iam.PolicyStatement(
            actions=["lambda:InvokeFunction"],
            resources=[f"arn:aws:lambda:{self.region}:{self.account}:function:advcomp-knowledge-base-*"]
        )
        gateway_role.add_to_policy(lambda_invoke_policy)
        
        # Add Bedrock Knowledge Base permissions to existing Lambda role if it exists
        if self.lambda_role_exists:
            # For imported roles, we can't add policies directly in CDK
            # The deploy.py script will handle this with fix_lambda_permissions()
            logger.info("Existing Lambda role found - permissions will be added by deploy script")
        else:
            # For new roles, we already added the permissions above
            logger.info("New Lambda role created with Bedrock permissions")
        
        # Grant S3 bucket access to the roles for all domain buckets
        for domain, bucket in domain_buckets.items():
            try:
                bucket.grant_read_write(agent_role)
            except Exception as e:
                logger.warning(f"Could not grant S3 access to agent role for {domain} bucket: {e}")
                
            try:
                bucket.grant_read_write(mcp_role)
            except Exception as e:
                logger.warning(f"Could not grant S3 access to MCP role for {domain} bucket: {e}")
                
            try:
                bucket.grant_read(gateway_role)
            except Exception as e:
                logger.warning(f"Could not grant S3 access to gateway role for {domain} bucket: {e}")
                
            try:
                bucket.grant_read(lambda_role)
            except Exception as e:
                logger.warning(f"Could not grant S3 access to lambda role for {domain} bucket: {e}")
        
        # Lambda invoke permissions are now added directly when creating the gateway role
        
        # Add resource-based policy to Lambda function to allow Gateway to invoke it
        try:
            self.lambda_function.add_permission(
                "GatewayInvokePermission",
                principal=iam.ServicePrincipal("bedrock-agentcore.amazonaws.com"),
                action="lambda:InvokeFunction"
            )
        except Exception as e:
            logger.warning(f"Could not add permission to Lambda function: {e}")
        
        # Import existing ECR repository for agent
        agent_repo = ecr.Repository.from_repository_name(
            self, "AgentRepository",
            repository_name="advcomp-agent"
        )
        
        # Build agent Docker image using CDK
        agent_image = ecr_assets.DockerImageAsset(
            self, "AgentImage",
            directory="./agent",
            platform=ecr_assets.Platform.LINUX_ARM64
        )
        
        # Deploy image to dedicated repository
        ecr_deployment = ecr_deploy.ECRDeployment(
            self, "DeployAgentImage",
            src=ecr_deploy.DockerImageName(agent_image.image_uri),
            dest=ecr_deploy.DockerImageName(f"{agent_repo.repository_uri}:latest")
        )
        

        
        # Create Cognito user pool for Gateway OAuth authentication
        user_pool = cognito.UserPool(
            self, "GatewayUserPool",
            user_pool_name="advcomp-gateway-pool",
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # Create resource server for OAuth scopes
        resource_server = cognito.UserPoolResourceServer(
            self, "GatewayResourceServer",
            user_pool=user_pool,
            identifier="gateway-api",
            scopes=[
                cognito.ResourceServerScope(scope_name="invoke", scope_description="Invoke gateway")
            ]
        )
        
        # Create OAuth app client with client_credentials flow
        app_client = user_pool.add_client(
            "GatewayOAuthClient",
            generate_secret=True,
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(client_credentials=True),
                scopes=[cognito.OAuthScope.resource_server(resource_server, cognito.ResourceServerScope(scope_name="invoke", scope_description="Invoke gateway"))]
            )
        )
        
        # Create Cognito domain for token endpoint
        domain = user_pool.add_domain(
            "GatewayDomain",
            cognito_domain=cognito.CognitoDomainOptions(
                domain_prefix=f"advcomp-gateway-{self.account}"
            )
        )
        
        from aws_cdk import aws_secretsmanager as secretsmanager, SecretValue
        # Create secret with OAuth credentials
        agent_secret = secretsmanager.Secret(
            self, "AgentOAuthSecret",
            secret_name="advcomp-agent-cognito",
            secret_object_value={
                "client_id": SecretValue.unsafe_plain_text(app_client.user_pool_client_id),
                "client_secret": app_client.user_pool_client_secret,
                "token_endpoint": SecretValue.unsafe_plain_text(f"https://{domain.domain_name}.auth.{self.region}.amazoncognito.com/oauth2/token"),
                "scope": SecretValue.unsafe_plain_text("gateway-api/invoke")
            },
            removal_policy=RemovalPolicy.DESTROY
        )
        agent_secret.grant_read(agent_role)
        
        # Gateway with CUSTOM_JWT using OAuth client
        gateway = agentcore.CfnGateway(
            self, "Gateway",
            name="advcomp-gateway-cdk",
            authorizer_type="CUSTOM_JWT",
            protocol_type="MCP",
            role_arn=gateway_role.role_arn,
            authorizer_configuration=agentcore.CfnGateway.AuthorizerConfigurationProperty(
                custom_jwt_authorizer=agentcore.CfnGateway.CustomJWTAuthorizerConfigurationProperty(
                    discovery_url=f"https://cognito-idp.{self.region}.amazonaws.com/{user_pool.user_pool_id}/.well-known/openid-configuration",
                    allowed_clients=[app_client.user_pool_client_id]
                )
            ),
            description="Gateway for Advanced Computing Team Collaboration Swarm"
        )
        gateway.node.add_dependency(resource_server)
        gateway.node.add_dependency(app_client)
        
        # Create Gateway Target for Lambda
        gateway_target = agentcore.CfnGatewayTarget(
            self, "GatewayTarget",
            gateway_identifier=gateway.ref,
            name="knowledge-base-query",
            credential_provider_configurations=[
                agentcore.CfnGatewayTarget.CredentialProviderConfigurationProperty(
                    credential_provider_type="GATEWAY_IAM_ROLE"
                )
            ],
            target_configuration=agentcore.CfnGatewayTarget.TargetConfigurationProperty(
                mcp=agentcore.CfnGatewayTarget.McpTargetConfigurationProperty(
                    lambda_=agentcore.CfnGatewayTarget.McpLambdaTargetConfigurationProperty(
                        lambda_arn=self.lambda_function.function_arn,
                        tool_schema=agentcore.CfnGatewayTarget.ToolSchemaProperty(
                            inline_payload=[
                                agentcore.CfnGatewayTarget.ToolDefinitionProperty(
                                    name="query_knowledge_base",
                                    description="Query domain-specific knowledge bases for AWS documentation",
                                    input_schema=agentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                                        type="object",
                                        properties={
                                            "domain": agentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                                                type="string",
                                                description="Domain to query (hpc, quantum, genai, visual, spatial, iot, partners)"
                                            ),
                                            "query": agentcore.CfnGatewayTarget.SchemaDefinitionProperty(
                                                type="string",
                                                description="Query text"
                                            )
                                        },
                                        required=["domain", "query"]
                                    )
                                )
                            ]
                        )
                    )
                )
            )
        )
        gateway_target.node.add_dependency(gateway)
        
        # Output Gateway URL and ID
        CfnOutput(self, "GatewayUrl", value=gateway.attr_gateway_url, export_name=f"{self.stack_name}-GatewayUrl")
        CfnOutput(self, "GatewayId", value=gateway.ref, export_name=f"{self.stack_name}-GatewayId")
        
        # Create AgentCore Memory for conversation persistence
        memory = agentcore_alpha.Memory(
            self, "SwarmMemory",
            memory_name="AdvCompSwarm_STM",
            description="Memory for Advanced Computing Team Collaboration Swarm",
            expiration_duration=Duration.days(90),
            memory_strategies=[
                agentcore_alpha.MemoryStrategy.using_built_in_semantic()
            ]
        )
        CfnOutput(self, "MemoryId", value=memory.memory_id, export_name=f"{self.stack_name}-MemoryId")
        
        # Create Agent Runtime using alpha library (after Gateway is created)
        agent_runtime = agentcore_alpha.Runtime(
            self, "AgentRuntime",
            runtime_name="advcomp_swarm_cdk",
            agent_runtime_artifact=agentcore_alpha.AgentRuntimeArtifact.from_ecr_repository(
                agent_repo, "latest"
            ),
            execution_role=agent_role,
            network_configuration=agentcore_alpha.RuntimeNetworkConfiguration.using_public_network(),
            description="Advanced Computing Team Collaboration Swarm Runtime",
            environment_variables={
                "GATEWAY_URL": gateway.attr_gateway_url,
                "AWS_REGION": self.region,
                "BEDROCK_MODEL_ID": "us.anthropic.claude-sonnet-4-5-20250929-v1:0",
                "MEMORY_ENABLED": "true",
                "MEMORY_ID": memory.memory_id,
                "COGNITO_SECRET_ARN": agent_secret.secret_arn
            }
        )
        agent_runtime.node.add_dependency(ecr_deployment)
        agent_runtime.node.add_dependency(gateway)
        agent_runtime.node.add_dependency(memory)
        
        # Note: DEFAULT endpoint is automatically created by AgentCore
        # Add a production endpoint that points to version 1
        prod_endpoint = agent_runtime.add_endpoint(
            "prod",
            version="1",
            description="Production endpoint for Advanced Computing Swarm"
        )
        
        # Output agent image URI, runtime ARN, and endpoint info
        CfnOutput(self, "AgentImageUri", value=f"{agent_repo.repository_uri}:latest", export_name=f"{self.stack_name}-AgentImageUri")
        CfnOutput(self, "AgentRepoName", value=agent_repo.repository_name, export_name=f"{self.stack_name}-AgentRepoName")
        CfnOutput(self, "AgentRuntimeArn", value=agent_runtime.agent_runtime_arn, export_name=f"{self.stack_name}-AgentRuntimeArn")
        CfnOutput(self, "AgentEndpointName", value="DEFAULT", export_name=f"{self.stack_name}-AgentEndpointName", description="Use DEFAULT endpoint (auto-created) or 'prod' for production")
        CfnOutput(self, "AgentProdEndpointArn", value=prod_endpoint.agent_runtime_endpoint_arn, export_name=f"{self.stack_name}-AgentProdEndpointArn")
        
        # Create Knowledge Bases using generative-ai-cdk-constructs
        domain_knowledge_bases = {}
        
        for domain in domains:
            kb = bedrock.VectorKnowledgeBase(
                self, f"{domain.capitalize()}KB",
                embeddings_model=bedrock.BedrockFoundationModel.TITAN_EMBED_TEXT_V1,
                instruction=f"Use this knowledge base to answer questions about {domain}."
            )
            
            bedrock.S3DataSource(
                self, f"{domain.capitalize()}DataSource",
                bucket=domain_buckets[domain],
                knowledge_base=kb,
                data_source_name=f"advcomp-{domain}-ds",
                chunking_strategy=bedrock.ChunkingStrategy.FIXED_SIZE
            )
            
            domain_knowledge_bases[domain] = kb
            
            CfnOutput(self, f"{domain.capitalize()}KnowledgeBaseId",
                     value=kb.knowledge_base_id,
                     export_name=f"{self.stack_name}-{domain.capitalize()}KBId")
        
        # Output bucket names
        for domain, bucket in domain_buckets.items():
            CfnOutput(self, f"{domain.capitalize()}KnowledgeBucketName", value=bucket.bucket_name)
        
        # Export the role ARNs, domain bucket names, ECR repositories, and Cognito resources for use in deploy.py
        self.agent_role_arn = agent_role.role_arn
        self.mcp_role_arn = mcp_role.role_arn
        self.gateway_role_arn = gateway_role.role_arn
        self.lambda_role_arn = lambda_role.role_arn
        self.domain_bucket_names = {domain: bucket.bucket_name for domain, bucket in domain_buckets.items()}
        self.agent_repo_uri = agent_repo.repository_uri
        self.agent_repo_name = agent_repo.repository_name
        self.agent_image_uri = f"{agent_repo.repository_uri}:latest"
        
        # Update Lambda with KB IDs
        for domain, kb in domain_knowledge_bases.items():
            self.lambda_function.add_environment(
                f"{domain.upper()}_KNOWLEDGE_BASE_ID",
                kb.knowledge_base_id
            )
        
        # Grant Lambda function access to all knowledge base buckets
        for domain, bucket in domain_buckets.items():
            bucket.grant_read(self.lambda_function)
