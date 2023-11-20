from flask import Flask, jsonify, request
import utils as utils
from pubsub import pub


app = Flask(__name__)


@app.route("/register-suites", methods=["POST"])
def register_suites():
    try:
        suites = utils.register_suites(request.data)
        for s in suites:
            pub.sendMessage("device_deployer", suite=s)

        return jsonify({"message": f"Registered {len(suites)} suites"})
    except Exception as e:
        return jsonify({"message": f"Failed to register suites, error: {e}"})


if __name__ == "__main__":
    # Subscribe to the 'device_deployer' topic with the queue listener function
    pub.subscribe(utils.queue_listener, "device_deployer")

    # Run flask app
    app.run(debug=True)
