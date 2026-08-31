# Python Flask Framework — CRUD API for Pixel Count → Counter App

A pixel-based API app for CRUD counters, duplicate-safe petition/form tracking, and API-key authorized counter creation.

                    ┌────────────────────────┐
                    │ Incoming request       │
                    │ /count or /count_pixel │
                    └──────────────┬─────────┘
                                   │
                           Read Query Params
                 name(id), donation, email_hash
                                   │
                                   ▼
                    ┌────────────────────────┐
                    │ Validate API Key       │
                    └──────────────┬─────────┘
                                   │
                 YES valid         │        NO invalid
                                   ▼
                           Proceed request       ───────────▶ Error 403
                                   │
                                   ▼
                    ┌────────────────────────┐
                    │ Validate domain/path/IP│
                    └──────────────┬─────────┘
                                   │
                       Allowed     │     Blocked
                                   ▼
                           Proceed            ───────────▶ Error 400
                                   │
                                   ▼
                    ┌────────────────────────┐
                    │ Validate counter exists│
                    │ name=id in Firestore   │
                    └──────────────┬─────────┘
                                   │
                     Exists        │       Missing
                                   ▼
                           Proceed            ───────────▶ Error 404
                                   │
                                   ▼
                    ┌─────────────────────────────┐
                    │ Email_hash duplicate check  │
                    └──────────────┬──────────────┘
                                   │
            Duplicate (already counted) │ Unique
                                   ▼
      Return 200 (Already counted)      │
                                   │     ▼
                                   │ Record email_hash
                                   │
                                   ▼
                    ┌────────────────────────┐
                    │ Increment counter      │
                    └──────────────┬─────────┘
                                   │
                           Success │  Failure (should never fail)
                                   ▼
                                 Done
                                   │
                           Return JSON or GIF


## Counter App — What’s New

- **Duplicate safety tightened** using `name + email_hash` as a unique key combination
- **Multiple email hashes can count toward the same counter**, enabling petition/form flexibility
- **API Key authentication added** to bypass origin/IP restrictions for authorized external requests
- **New endpoint added to create counters remotely** via API request
- **NRO Management System added**: Centralized management of National/Regional Offices (NROs) in the Admin section.
- **Dynamic NRO Dropdowns**: Replaced manual NRO text fields with dropdowns populated from active NRO records.
- **Multi-User counter assignment**: Ability to assign multiple specific users to a single counter for collaborative management.
- **Advanced Access Control**: Visibility logic now combines ownership, NRO affiliation, and manual assignments.
- **Enhanced UI Integration**: Integrated **DataTables** and **Switchery** for premium, interactive management of NROs and Counters.
- **Admin API Key Visibility**: Administrators can now see all API keys in the system, including the user they belong to.
- **Improved and consistent error messages** returned for all validation failures
- **All assets and libraries load locally (no external CDN/CDN calls)** for maximum availability and sustainability
- Running serverless on **Google Cloud Run** with auto-scaling and efficient compute best practices

## Create a counter through the API

Send a `POST` request to `/api/createcounter`. Supply the API key in the
`apikey` query parameter (or the `X-API-Key` header) and supply the counter
fields as a JSON request body.

```bash
curl --request POST \
  'http://localhost:8080/api/createcounter?apikey=<apikey>' \
  --header 'Content-Type: application/json' \
  --data '{
    "name": "gpaotest3",
    "campaign": "Test Campaign",
    "contactpoint": "aaksoy@greenpeace.org",
    "count": 0,
    "nro": "gpao",
    "type": "global",
    "url": "https://action.greenpeace.org/petition/test",
    "user": "<user_name>",
    "uuid": ""
  }'
```

The first request for a counter name creates the counter and returns `201
Created`:

```json
{
  "counter_name": "gpaotest3",
  "message": "Counter created successfully"
}
```

Counter names are unique. A subsequent request with the same `name` is
rejected with `409 Conflict`, and no additional counter is created:

```json
{
  "error": "Counter ID already exists"
}
```


# NRO Management
The NRO (National/Regional Office) Management system allows administrators to control the official offices used throughout the application.

- **Centralized Control**: Register new NROs or edit existing ones via the Admin sidebar.
- **Active/Inactive Status**: Use the **Switchery slider** in the NRO list to activate or deactivate offices. Inactive offices are automatically filtered out from counter creation and user profile selection.
- **UI Performance**: The NRO table uses **DataTables** for instant search and efficient pagination across large office lists.

# Multi-User Access & Visibility Logic
Counter visibility is now smarter and supports collaborative work within and across offices.

### Visibility Rules
A user will see a counter in their list if they meet **any** of the following conditions:
1. **Administrators**: See everything.
2. **Owners**: You created the counter (matching `uuid`).
3. **Global**: The counter is marked as `type: global`.
4. **NRO Local**: The counter is `type: local` and its `nro` matches the user's assigned NRO.
5. **Manually Assigned**: The user is explicitly selected in the **"Assigned Users"** multi-select field on the counter.

### Assigning Users
When creating or editing a counter, use the **Assigned Users (Multi-select)** field to grant access to specific team members who might not be in your NRO or who aren't the primary owner. 
*(Tip: Hold Ctrl/Cmd to select multiple people)*


# How it works

This is an API driven pixel approach based on the CRUD API concept.

## API Key Behavior

| Request Variant | Result |
|---|---|
| Valid API key + active | Request allowed |
| Valid API key + inactive | Returns **"API key inactive"** |
| Invalid API key | Returns **"API key not found"** |
| No API key | Returns **"Missing API key"** |
| API key included in request | Bypasses origin/IP restrictions |

You can pass API keys via:
- `apikey` query parameter
- `X-API-Key` request header

Example:
http://localhost:8080/count_pixel?id=<counter>&email_hash=<hash>&apikey=<apikey>


###
### The API endpoint allows the user to get the endpoint total defined  by id
    API endpoint /signup?id=<id>

    example: http://localhost:8080/signup?id=<counter_name>

## Duplicate & Counter Behavior Logic

- A `name + email_hash` record is **blocked** if it already exists.
- `name + email_hash` data is **never written** if the counter doesn't exist.
- If a counter does **not** exist, a new counter **can be created** when a valid API key is present.
- When a bad counter name is sent to a **count endpoint**, the app returns `"Counter not found"` instead of storing a duplicate block record.

## API Routes

### ➕ Add Counter (Fallback GET and POST)

**POST JSON body**
```json
{
  "id": "<counter_name>",
  "count": 0
}
GET fallback (when POST is not possible)
```

## Show counter using iframe
To increase the counter you will put a pixel on the thank you page of the petition. Be careful that it is used only when someone has signed the petition. The pixel is practically invisible. The html code to put it is:

<iframe src="http://localhost/count?id=<counter_name>" width="1" height="1" frameborder=0 style="overflow:hidden;" scrolling="no"></iframe>

# Error messages and where they are triggered

### **Request Validation Errors**

| Message | Location / Logic |
|---|---|
| `"Disallowed request"` | is_allowed_request() / is_allowed_request() |
| `"Missing counter id"` | if no `id=` is provided |
| `"Counter not found"` | when counter lookup returns empty |
| `"Duplicate: counter + email_hash already counted"` | process_email_hash() |
| `"Email hash cannot be stored for missing counter"` | if counter does *not* exist |
| `"Invalid counter name"` | when `name` format fails sanitization/lookup |
| `"Unauthorized access"` | API key wrapper when key missing/invalid |
| `403 + {"error":"Unauthorized","reason":<reason>}` | returned by require_valid_api_key() |

### **Pixel Response Errors**

| Message | Condition |
|---|---|
| `"An error occurred generating pixel"` | send_file() fails |
| `"Internal handler error"` | uncaught exceptions return 500 |

### **API Key Errors**

| Message | Trigger |
|---|---|
| `"Missing API key"` | validate_api_key() |
| `"API key not found"` | key lookup returns no doc |
| `"API key inactive"` | key exists but `active == False` |
| `"Unauthorized"` | Wrapper returns `403` |


# Build and launch to Cloud Run

# Deploy
Log in to gcloud as the user that will run Docker commands. To configure authentication with user credentials, run the following command:

```
gcloud auth login
```

To configure authentication with service account credentials, run the following command:

```
gcloud auth activate-service-account ACCOUNT --key-file=KEY-FILE
```

```
gcloud auth activate-service-account <ypur service account name>@<project-id>.iam.gserviceaccount.com --key-file=<location to your service account>
```

Where

ACCOUNT is the service account name in the format 
```
[USERNAME]@[PROJECT-ID].iam.gserviceaccount.com. 
```

## You need to Enable the following Google apis

Enable Firestore Database
Enable Cloud Resource Manager API
Enable Identity and Access Management (IAM) API
Enable Cloud Run Admin API 

# Setup Secret Manager

These are the names of secrets variable the application expect being set

client-secret-key - as it say the secret key from the Oauth setup
app_secret_key - this is an application secret can be anything you want
restrciteddomain - this is the domain name for were the application will limited the lgon from

# Create an Oauth with web application flow


# Service Accounts

You can view existing service accounts on the Service Accounts page of console or with the command gcloud iam service-accounts list

KEY-FILE is the service account key file. See the Identity and Access Management (IAM) 

documentation for information about creating a key.

Configure Docker with the following command:

```
gcloud auth configure-docker
```
<a href="https://cloud.google.com/compute/docs/regions-zones/#available">Regions and zones</a>

<a href="https://cloud.google.com/container-registry/docs/pushing-and-pulling">Pushing and pulling images</a>

Europe Docker is the Docker registry that is used for the Docker image.
```
$ docker build -t eu.gcr.io/<project-id>/pixelcount .
$ docker push eu.gcr.io/<project-id>/pixelcount
```

US
```
$ docker build -t us.gcr.io/<project-id>/pixelcount .
$ docker push us.gcr.io/<project-id>/pixelcount
```

#
# Building a docker image on a Apple M1 for Google Cloud linux/am64
#

Option A: buildx
Buildx is a Docker plugin that allows, amongst other features, to build multi-platform images.

We are developing on the Mac ARM architecture but we want to create a x86 compatible image. The solution is NOT to use the heroku:container push command but rather building the image locally with Docker buildx.

```
docker buildx build \
--platform linux/amd64 \
--push \
-t eu.gcr.io/make-smthng-website/pixelcounter:v0.1 .
```


export GOOGLE_APPLICATION_CREDENTIALS=key.json
docker login -u _json_key -p "`cat ${GOOGLE_APPLICATION_CREDENTIALS}`" https://eu.gcr.io

As you can see I am tagging for each new version with adding:v<number> like this pixelcount:v2

This allows me to modifying the image without having to rebuild it.

You would need to update the terraform main/tf file so the tag matches.


Option B: set DOCKER_DEFAULT_PLATFORM
The DOCKER_DEFAULT_PLATFORM environment variable permits to set the default platform for the commands that take the --platform flag.

```
export DOCKER_DEFAULT_PLATFORM=linux/amd64
```

## Deploy with Yaml - work in progress
```
gcloud builds submit --config cloudbuild.yaml .
```

# Push To Multiple Git Repositories

I use two git Repositories
    GitLab for internal Use and deployment
    GitHub for public open source code sharing

From the root folder of your project, add both repositories to the remotes:

```
git remote add origin <GitLab URL>
git remote add copy <GitHUb URL>

Run the git remote -v command to ensure that both remotes were successfully added

Now you are able to perform a push to the selected remote by specifying it in the git push command:

```
git push origin master
git push copy master
```

Create a new remote named "all", and add GitLab and GitHub URLs to it

```
git remote add all <GitLab URL>```
git remote set-url all --add --push <GitLab URL>
git remote set-url all --add --push <GitHub URL>
```

```
git push all main
```

# Get project iam ploicy

```
gcloud projects get-iam-policy <project_id>

gcloud iam service-accounts create pixelcounter-deploy@make-smthng-website.iam.gserviceaccount.com \
    --description="DESCRIPTION" \
    --display-name="DISPLAY_NAME"
