import boto3
import botocore.exceptions

# === Configuration === #
STACK_NAME = "ProgressTrackerStack"
BUCKET_NAME = "s33ding-progress"
TABLE_NAME = "ProgressTracker"
INDEX_DOCUMENT = "index.html"

# === CloudFormation Template === #
template_body = f'''
AWSTemplateFormatVersion: '2010-09-09'
Resources:
  ProgressBucket:
    Type: AWS::S3::Bucket
    Properties:
      BucketName: {BUCKET_NAME}
      WebsiteConfiguration:
        IndexDocument: {INDEX_DOCUMENT}
      PublicAccessBlockConfiguration:
        BlockPublicAcls: true
        BlockPublicPolicy: false
        IgnorePublicAcls: true
        RestrictPublicBuckets: false

  ProgressBucketPolicy:
    Type: AWS::S3::BucketPolicy
    Properties:
      Bucket: !Ref ProgressBucket
      PolicyDocument:
        Version: \"2012-10-17\"
        Statement:
          - Effect: Allow
            Principal: '*'
            Action: 's3:GetObject'
            Resource: !Sub 'arn:aws:s3:::{BUCKET_NAME}/*'

  ProgressTable:
    Type: AWS::DynamoDB::Table
    Properties:
      TableName: {TABLE_NAME}
      AttributeDefinitions:
        - AttributeName: ItemID
          AttributeType: S
        - AttributeName: Timestamp
          AttributeType: S
      KeySchema:
        - AttributeName: ItemID
          KeyType: HASH
        - AttributeName: Timestamp
          KeyType: RANGE
      BillingMode: PAY_PER_REQUEST
'''

def deploy_stack():
    cf = boto3.client('cloudformation')
    try:
        print("Checking if stack exists...")
        cf.describe_stacks(StackName=STACK_NAME)
        print(f"Stack '{STACK_NAME}' already exists.")
        return
    except botocore.exceptions.ClientError as e:
        if 'does not exist' not in str(e):
            raise
        print("Stack does not exist. Creating now...")

    response = cf.create_stack(
        StackName=STACK_NAME,
        TemplateBody=template_body,
        Capabilities=['CAPABILITY_NAMED_IAM']
    )
    print("Stack creation initiated...")
    waiter = cf.get_waiter('stack_create_complete')
    waiter.wait(StackName=STACK_NAME)
    print(f"Stack '{STACK_NAME}' created successfully.")

def main():
    deploy_stack()

if __name__ == '__main__':
    main()

