from flask import Blueprint, render_template, url_for, request
import json
import requests
import ssl

app_blueprint = Blueprint('app_blueprint', __name__)

def findPropertyInfo(latitude, longitude, jobber_house_number, err_radius, created_client_id, token):
	query_string = f"http://data.edmonton.ca/resource/q7d6-ambg.json?$where=within_circle(point_location, {latitude}, {longitude}, {err_radius})&$limit=10"
	results = requests.get(query_string).json()
	for client_property in results:
		try:
			type(client_property['street_name'])
		except KeyError:
			print("No street")

		try:
			if client_property['house_number'] == jobber_house_number:
				yearBuilt, zoning, lotSize = extraPropertyInfo(client_property['account_number'])
				return postOutJobberData(client_property, created_client_id, yearBuilt, zoning, lotSize, token)
		except KeyError:
			print("No house number")

	if err_radius < 420:
		err_radius += 100
		print("expanding search")
		return findPropertyInfo(latitude, longitude, jobber_house_number, err_radius, created_client_id, token)
	else:
		return "No matching property"

def extraPropertyInfo(account_number):
	query_string = f"https://data.edmonton.ca/resource/dkk9-cj3x.json?account_number={account_number}"
	try: 
		results = requests.get(query_string).json()[0]
		print("results", results)

		return results["year_built"], results["zoning"], results["lot_size"]
	except TypeError:
		print("No extra info")
		return "No extra info", "No extra info", "No extra info"
		

def postOutJobberData(found_property, created_client_id, yearBuilt, zoning, lotSize, token):
	my_currency = int(found_property["assessed_value"])
	desired_representation = "{:,}".format(my_currency)

	customFieldMutation = f"""
		mutation createNote {{
		clientEdit(clientId: "{created_client_id}", input: {{customFields: 
			[
			{{customFieldConfigurationId: "Z2lkOi8vSm9iYmVyL0N1c3RvbUZpZWxkQ29uZmlndXJhdGlvblRleHQvMTc2OTA0Mw==", valueText: "${desired_representation} 🤑"}}
			{{customFieldConfigurationId: "Z2lkOi8vSm9iYmVyL0N1c3RvbUZpZWxkQ29uZmlndXJhdGlvblRleHQvMTc2OTA1Mg==", valueText: "{found_property["neighbourhood"]}"}}
			{{customFieldConfigurationId: "Z2lkOi8vSm9iYmVyL0N1c3RvbUZpZWxkQ29uZmlndXJhdGlvblRleHQvMTc2OTE2OQ==", valueText: "{yearBuilt}"}}
			{{customFieldConfigurationId: "Z2lkOi8vSm9iYmVyL0N1c3RvbUZpZWxkQ29uZmlndXJhdGlvblRleHQvMTc2OTE3Mw==", valueText: "{zoning}"}}
			{{customFieldConfigurationId: "Z2lkOi8vSm9iYmVyL0N1c3RvbUZpZWxkQ29uZmlndXJhdGlvblRleHQvMTc2OTE3NA==", valueText: "{lotSize}"}}
			]
		}}) {{
			client {{
			customFields {{
				... on CustomFieldText {{
				id
				valueText
				}}
			}}
			}}
		}}
		}}

	"""

	headers = {"Authorization": f"Bearer {token}",
			    "X-JOBBER-GRAPHQL-VERSION": "2023-05-05"}
				
	response = requests.post(url="https://api.getjobber.com/api/graphql",
								data={"query": customFieldMutation},
								headers=headers
						)
	print("------------------")
	client = response.json()
	print(client)

	print("Client", client["data"])

	response.close()

	return


def formatIncJobberData(created_client_id, token):
	gqlquery = f"""query findClient {{
			client(id: "{created_client_id}") 
				{{ clientProperties {{
					edges {{
						node {{
							address {{
							street1
							coordinates {{
								point
							}}
          				}}
        			}}
      			}}
    		}}
  		}} 
	}}"""

	headers = {"Authorization": f"Bearer {token}",
			    "X-JOBBER-GRAPHQL-VERSION": "2023-05-05"}
				
	response = requests.post(url="https://api.getjobber.com/api/graphql",
								data={"query": gqlquery},
								headers=headers
							)
	propertyData = response.json()
	response.close()

	coordinates = propertyData["data"]["client"]["clientProperties"]["edges"][0]["node"]["address"]["coordinates"]["point"].split(", ")
	latitude = coordinates[0]
	longitude = coordinates[1]
	jobber_house_number = propertyData["data"]["client"]["clientProperties"]["edges"][0]["node"]["address"]["street1"].split(" ")[0]

	return latitude, longitude, jobber_house_number



@app_blueprint.route("/", methods=["GET", "POST"])
def index():
	if request.method == "POST":
		token = request.headers.get("Authorization")
		jobber_webhook_payload = json.loads(request.data)
		print("received payload", jobber_webhook_payload)
		created_client_id = jobber_webhook_payload['data']['webHookEvent']['itemId']
		latitude, longitude, jobber_house_number = formatIncJobberData(created_client_id, token)
		findPropertyInfo(latitude, longitude, jobber_house_number, 50, created_client_id, token)
		return "OK I put that into Jobber"
	else:
		# demo data: our fallback data when accessing page without webhook
		return findPropertyInfo("53.541883", "-113.4980533", "10130", 10, "MjI2NjU5NzU=", token)
	