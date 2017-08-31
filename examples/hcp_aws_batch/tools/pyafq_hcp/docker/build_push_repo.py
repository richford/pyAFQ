import boto3
import docker
from shutil import copyfile
import datetime
import os
import sys
from argparse import ArgumentParser
import subprocess

def build_and_push(repo_name, buildpath, dockerfile, reqpath=None,
        tags=['latest'], verbose_docker=False):

    # Refresh the aws ecr login credentials
    login_cmd = subprocess.check_output(['aws', 'ecr', 'get-login',
        '--no-include-email', '--region', 'us-east-1'])
    login_result = subprocess.call(
            login_cmd.decode('ASCII').rstrip('\n').split(' '))

    ecr_client = boto3.client('ecr')

    # Get repository uri
    try:
        # First, check to see if it already exists
        response = ecr_client.describe_repositories(
                repositoryNames=[repo_name])
        repo_uri = response['repositories'][0]['repositoryUri']
        print('Repository {name:s} already exists at {uri:s}'.format(
            name=repo_name, uri=repo_uri))
    except ecr_client.exceptions.RepositoryNotFoundException:
        # If it doesn't create it
        response = ecr_client.create_repository(
                repositoryName=repo_name)
        repo_uri = response['repository']['repositoryUri']
        print('Created repository {name:s} at {uri:s}'.format(
            name=repo_name, uri=repo_uri))

    if reqpath and not os.path.isfile(buildpath + '/requirements.txt'):
        copyfile(reqpath, buildpath + '/requirements.txt')

    c = docker.from_env()

    if not tags:
        tags = ['latest']

    for tag in tags:
        print('Building image with tag {tag:s}'.format(tag=tag))
        build_result = c.build(path=buildpath, dockerfile=dockerfile,
                tag=repo_name + ':' + tag)
        if verbose_docker:
            for line in build_result:
                print(line)

        print('Tagging image with tag {tag:s}'.format(tag=tag))
        c.tag(image=repo_name + ':' + tag, repository=repo_uri, tag=tag)

        print('Pushing image with tag {tag:s}'.format(tag=tag))
        push_result = c.push(repository=repo_uri, tag=tag)
        if verbose_docker:
            print(push_result)


    if reqpath and not os.path.isfile(buildpath + '/requirements.txt'):
        os.remove(buildpath + '/requirements.txt')

    return repo_name, repo_uri


def main():
    description = 'Build a docker image and push it to a repository'
    argparser = ArgumentParser(description=description)

    argparser.add_argument('-n', '--repo-name', dest='repo_name', type=str,
            help='Repository Name', required=True)
    argparser.add_argument('-t', '--tags', nargs='+', type=str,
            help='List of repository tags (space separated)', required=False)
    argparser.add_argument('-r', '--reg-id', dest='reg_id', type=str,
            help='Registry ID', required=False)
    argparser.add_argument('--reqpath', type=str,
            help='Path to requirements.txt file', required=False)
    argparser.add_argument('-d', '--dockerfile', type=str,
            help='Path to dockerfile', required=False, default='./Dockerfile')
    argparser.add_argument('-p', '--buildpath', type=str,
            help='Docker buildpath', required=False, default='.')
    argparser.add_argument('-v', '--verbose', dest='verbose',
            help='Get verbose Docker output', action='store_true')

    args = argparser.parse_args()

    verbose = False
    if args.verbose:
        verbose = True

    # Convert relative paths for Dockerfile and build path to absolute paths
    dockerfile = os.path.abspath(args.dockerfile)
    buildpath = os.path.abspath(args.buildpath)
    if args.reqpath:
        reqpath = os.path.abspath(args.reqpath)
    else:
        reqpath = None

    if args.tags:
        tags = args.tags
    else:
        tags = ['latest']

    repo_name, repo_uri = build_and_push(repo_name=args.repo_name,
            buildpath=buildpath, dockerfile=dockerfile,
            reqpath=reqpath, tags=tags, verbose_docker=verbose)

    print('Docker image built and pushed')
    print('Here is the repository URI:')
    print(repo_uri)
    
if __name__ == '__main__':
    main()
