import json
import time
import random
from datetime import datetime

boto3 = None  # Simulate aws SDK
ssh = None  # Simulate ssh client
MongoClient = None  # Simulate mongodb client


# Log to console
def log(message):
    print(message)


# Generate a 5 digits id
def generate_id():
    id = ''.join(random.choices('0123456789', k=5))
    return id


# Tranform a list of devices dicts into a flat list containing all devices 
def expand_devices(devices):
    expanded_devices = []
    for device in devices:
        for _ in range(device["count"]):
            expanded_devices.append(
                {
                    "osType": device["osType"],
                    "osVersion": device["osVersion"],
                }
            )

    return expanded_devices


# Divide {devices} into chunks of {chunk_size}
def chunk_devices(devices, chunk_size=5):
    chunks = []
    for i in range(0, len(devices), chunk_size):
        chunks.append(devices[i : i + chunk_size])

    return chunks


# Parse register suites request payload json into python dict 
def parse_suite_json(json_string):
    try:
        data = json.loads(json_string)
    except json.JSONDecodeError:
        raise ValueError("Invalid JSON format")
    return data


# Parse suites payload and divide it into chunk
def register_suites(payload):
    try:
        parsed_payload = parse_suite_json(payload)
    except Exception as e:
        log(f"Failed to parse incoming suite, error: {e}")
        raise

    all_devices = expand_devices(parsed_payload["devices"])

    suites = [
        {
            "suiteName": parsed_payload["suiteName"],
            "exeBucketUri": parsed_payload["exeBucketUri"],
            "tenantId": parsed_payload["tenantId"],
            "dbUrl": parsed_payload["dbUrl"],
            "devices": chunk,
        }
        for chunk in chunk_devices(all_devices)
    ]

    return suites


# Listens to the 'device_deployer' topic and triggers the deployment of a test suite
def queue_listener(suite):
    log(f"Parsing new suite requests, {suite['suiteName']} with {len(suite['devices'])}")

    with open("./deploy_suite.sh", "r") as f:
        suite_deployment_script = f.read()

    for device in suite["devices"]:
        sid = generate_id()
        log(f"Starting test suite: {suite['suiteName']} (SID: {sid})")
        
        try:
            deploy_test_suite(
                suiteName=suite["suiteName"],
                device=device,
                exeBucketUri=suite["exeBucketUri"],
                dbUrl=suite["dbUrl"],
                tenantId=suite["tenantId"],
                suite_deployment_script=suite_deployment_script,
            )
            log(f"Test suite {suite['suiteName']} (SID: {sid}) finished succesfully")
        except Exception as e:
            log(f"Test suite {suite['suiteName']} (SID: {sid}) finished unsuccesfully")


# Deploys a test suite on an EC2 instance, executes it, and inserts logs to the MongoDB database.
def deploy_test_suite(suiteName, device, exeBucketUri, tenantId, dbUrl, suite_deployment_script):
    log(f"{suiteName}: Creating new device: {device['osType']} ({device['osVersion']})")

    start_timestamp = time.mktime(datetime.utcnow().timetuple())

    ec2 = boto3.resource("ec2")

    # Deploy a new EC2 instance
    log(f"{suiteName}: Deploying new ec2 instance ({device['osType']} - {device['osVersion']})")

    instance = ec2.create_instances(
        ImageId=device["osType"],
        InstanceType=device["osVersion"],  
        # In a real world scenario, device will store an actual image id & instanceType
        MinCount=1,
        MaxCount=1,
        KeyName="some-key-name",
    )[0]

    # Wait for the instance to start
    instance.wait_until_running()

    # Fetch the public DNS or IP to connect
    instance.load()
    public_dns = instance.public_dns_name

    # Connect to the instance and execute commands
    log(f"{suiteName}: Running suite deployment script")

    ssh.connect(public_dns, username="ec2-user", key_filename="your-key.pem")
    stdin, stdout, stderr = ssh.exec_command(f'bash -s -- {suite_deployment_script} "{exeBucketUri}" "{tenantId}"')

    # Wait until the script has finished executing
    output = stdout.read()
    error = stderr.read()
    exit_code = stdout.channel.recv_exit_status()
    end_timestamp = time.mktime(datetime.utcnow().timetuple())

    # Insert suite execution data into db
    log(f"{suiteName}: Suite finished execution (exitCode: {exit_code}), inserting session logs to db")

    try:
        mongo_client = MongoClient(dbUrl)  # Simulate mongodb client
        db = mongo_client["test_suites"]

        collection = db["devices"]
        new_document = {
            "deviceAddress": public_dns,
            "suiteOutput": output,
            "startTimestamp": start_timestamp,
            "endTimestamp": end_timestamp,
            "exitCode": exit_code,
        }
        inserted_id = collection.insert_one(new_document).inserted_id

        log(f"{suiteName}: Session logs inserted to db, document id: {inserted_id}")
    except Exception as e:
        log(f"Failed to insert session logs to db, error: {e}")

    log(f"{suiteName}: Shutting down instance")
    instance.terminate()
