import json
import requests
import boto3


def handler(event, context):
    print('request: {}'.format(json.dumps(event)))

    client = boto3.client('ssm')

    url = 'http://your-server-url:port/aws-poc-notify'

    api_key_response = client.get_parameter(
        Name='/job-trigger-lambda/api_key',
        WithDecryption=False
    )
    api_key = api_key_response['Parameter']['Value']

    payload = {
        'id': event['id'],
        'account': event['account']
    }
    headers = {
        'Content-Type': 'application/json',
        'API_KEY': api_key,
    }
    data = json.dumps(payload);
    r = requests.post(url=url,data=data,headers=headers)
    status_code = r.status_code

    if status_code < 200 or status_code > 299:
        raise Exception('status_code is {}'.format(status_code))

    return "OK"
