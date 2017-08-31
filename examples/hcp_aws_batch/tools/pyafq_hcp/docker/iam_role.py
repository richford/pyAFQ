import json
import boto3
from argparse import ArgumentParser

iam = boto3.client('iam')

def create_role_attach_policy(role_name='afqBatchJobRole',
        role_description='AFQ batch job role',
        policy_names=['AmazonS3FullAccess']):

    attach_role_policy = {
            "Version": "2012-10-17",
            "Statement": {
                "Sid": "",
                "Effect": "Allow",
                "Principal": {
                    "Service": "ecs-tasks.amazonaws.com"
                    },
                "Action": "sts:AssumeRole"
                }
            }

    try:
        response = iam.create_role(
                RoleName=role_name,
                AssumeRolePolicyDocument=json.dumps(attach_role_policy),
                Description=role_description
                )
        role_arn = response.get('Role')['Arn']
        print('Created role {name:s}'.format(name=role_name))
    except iam.exceptions.EntityAlreadyExistsException:
        response = iam.get_role(RoleName=role_name)
        role_arn = response.get('Role')['Arn']
        print('Role {name:s} already exists'.format(name=role_name))

    policy_response = iam.list_policies(Scope='AWS')
    for policy in policy_names:
        policy_arn = list(filter(lambda p: p['PolicyName'] == policy,
            policy_response.get('Policies')))[0]['Arn']
        response = iam.attach_role_policy(
                PolicyArn=policy_arn,
                RoleName=role_name)
        print('Attached policy {policy:s} to role {role:s}'.format(
            policy=policy, role=role_name))

    return role_name, role_arn


def main():
    description = 'Create an IAM role for AWS Batch jobs.'
    argparser = ArgumentParser(description=description)

    argparser.add_argument('-n', '--role-name', dest='role_name', type=str,
            help='Role name', required=False, default='afqBatchJobRole')
    argparser.add_argument('-p', '--policies', nargs='+', type=str,
            help='List of policy names (space separated)', required=False,
            default=['AmazonS3FullAccess'])
    argparser.add_argument('-d', '--role-description', dest='role_description',
            type=str, help='Role description', required=False,
            default='AFQ batch job role')

    args = argparser.parse_args()

    create_role_attach_policy(role_name=args.role_name,
            role_description=args.role_description,
            policy_names=args.policies)

if __name__ == '__main__':
    main()
