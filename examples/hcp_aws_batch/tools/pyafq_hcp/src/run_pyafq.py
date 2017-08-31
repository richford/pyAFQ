import AFQ
import boto3
from argparse import ArgumentParser
import platform

def main():
    client = boto3.resource('s3')

    argparser = ArgumentParser()
    argparser.add_argument('--index', type=str, help="It's an index silly",
            required=True)

    args = argparser.parse_args()

    host = platform.node()

    fn = 'temp_{i:03d}.txt'.format(i=int(args.index))
    with open(fn, 'w') as f:
        f.write("Hello World from index {i:s} on host {host:s}!".format(
            i=args.index, host=host))

    b = client.Bucket("fetch-and-run-bucket")
    b.upload_file(fn, fn)

if __name__ == "__main__":
    main()
