# Security

## Reporting Security Issues

If you discover a potential security issue in this project, please notify AWS Security via our [vulnerability reporting page](https://aws.amazon.com/security/vulnerability-reporting/). Please do **not** create a public GitHub issue.

## Important Notice

**This is sample code for demonstration purposes only.** It is not production-ready and should not be deployed to production environments without significant additional security hardening.

## Security Considerations

When adapting this sample for production use, consider these security practices:

### Authentication & Authorization

- **IAM Roles**: Components use IAM roles for service integration. Review and scope permissions further for production.
- **OAuth JWT Authentication**: Gateway uses OAuth 2.0 client credentials flow with Cognito
- **Automatic Token Management**: Agent retrieves short-lived JWT tokens automatically from Secrets Manager
- **Environment Variables**: Never commit `.env` files or credentials to version control

### Network Security

- **VPC Deployment**: Lambda functions use public network access in this sample
- **AgentCore Gateway**: Built-in JWT validation via Cognito OIDC discovery
- **Rate Limiting**: No rate limiting is configured in this sample

### Data Protection

- **Encryption in Transit**: All AWS service communications use TLS
- **Encryption at Rest**: Bedrock Knowledge Bases and AgentCore Memory encrypt data at rest
- **Sensitive Data**: This sample does not implement data classification or PII handling
- **OAuth Credentials**: Stored in AWS Secrets Manager

### AWS Service Configuration

- **Bedrock Model Access**: This sample uses model invocation permissions with wildcards
- **Knowledge Base Permissions**: Lambda function has broad Bedrock permissions
- **CloudWatch Logs**: Logging is enabled with default retention
- **Resource Policies**: Basic resource policies are configured

### Deployment Security

- **CDK Deployment**: CloudFormation templates are generated automatically
- **Docker Images**: No vulnerability scanning is configured in this sample
- **Dependencies**: Python dependencies are pinned to specific versions
- **Secrets Management**: OAuth credentials use AWS Secrets Manager

### Monitoring & Auditing

- **CloudTrail**: Not configured in this sample
- **CloudWatch Alarms**: Not configured in this sample
- **Cost Monitoring**: Not configured in this sample
- **Access Logs**: Basic CloudWatch logging is enabled

## Known Limitations

This is sample code for demonstration purposes:

- IAM permissions use wildcards in some cases - you may want to scope these further depending on your requirements
- Knowledge bases are created empty - documents must be uploaded manually
- Debug logging is enabled by default
- No rate limiting on agent invocations
- Response times can be 25-60 seconds for multi-expert queries

## Considerations for Production Adaptation

If you choose to adapt this sample for production use, you will need to evaluate and implement additional security controls based on your specific requirements. Some areas to consider may include (this list is not exhaustive):

- IAM permissions scoped to specific resources rather than wildcards
- Regular credential rotation
- Logging and auditing appropriate for your compliance requirements
- Network isolation (VPC, security groups, etc.)
- Rate limiting and throttling
- Monitoring and alerting
- Vulnerability scanning for containers and dependencies
- Data handling policies for sensitive information

Consult with your security team to determine the appropriate controls for your use case.

## Additional Resources

- [AWS Security Best Practices](https://aws.amazon.com/architecture/security-identity-compliance/)
- [Amazon Bedrock Security](https://docs.aws.amazon.com/bedrock/latest/userguide/security.html)
- [AWS Lambda Security](https://docs.aws.amazon.com/lambda/latest/dg/lambda-security.html)
- [Amazon Cognito Security](https://docs.aws.amazon.com/cognito/latest/developerguide/security.html)
