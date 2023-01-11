# Python Flask Framework - created a CRUD API for pixelcount
Create an CRUD pixel count API app.

# GCP Cloud Run Button

You can try to run it from this location

[![Run on Google Cloud](https://storage.googleapis.com/cloudrun/button.svg)](https://console.cloud.google.com/cloudshell/editor?shellonly=true&cloudshell_image=gcr.io/cloudrun/button&cloudshell_git_repo=https://github.com/greenpeace/TechLab-Pixel-Counter.git)

# How it works

This is an API driven pixel approach based on the CRUD API concept.

## Add
###
### API Route add a counter by ID - requires json file body with id and count
###
    This is a post command
    You can use multiple counters in the same database by changing the id of the counter name, like this
    
    ```
    {
    "id": "<counter_name>",
    "count": 0
    }
    ```
    Add is a post command

    example: http://localhost:8080/add?id=<counter_name>&count=0

#
# API Route add with GET a counter by ID - if you can not use POST we offer a GET option to adding a counter
    /addset?id=<counter_name>&count=<count>
    
    example: http://localhost:8080/addset?id=<counter_name>&count=0


## Read

#
# API Route list all or a speific counter by ID - requires json file body with id and count
#

    Read a specific counter by counter_name
    http://localhost:8080/list?id=<countname>

    Read all Counters - Displayed in Table format
    http://localhost:8080/list

## Update

###
### API Route Update a counter by ID - requires json file body with id and count
    API endpoint /update?id=<id>&count=<count>

    You can update a counter or reset it by
    example: http://localhost:8080/update?id=<counter_name>&count=<a number>

# Delete

###
### API Route Delete a counter by ID /delete?id=<id>
    API Enfpoint /delete?id=<countername>

    example: http://localhost:8080/delete?id=<countername>

# Other endpoints
## Increase Counter

### Count GET
###
### The count route used for pixel image to increase a count using a GET request
    API endpoint /count?id=<id>
    example: http://localhost:8080/count?id=<counter_name>

### Count POST
###
### API Route Increase Counter by ID - requires json file body with id and count
    API endpoint /counter 
    json {"id":"GP Canada","count", 0}

    example: http://localhost:8080/

###
### The API endpoint allows the user to get the endpoint total defined  by id
    API endpoint /signup?id=<id>

    example: http://localhost:8080/signup?id=<counter_name>

###
### The API endpoint is an example on how you can submit a donation form capture the data and submit it to a collection
    API endpoint /donationform
    Post request with json form data{"id":"<counter_name","count", 0}
    
    example: http://localhost:8080/donationform

## Show counter using iframe
To increase the counter you will put a pixel on the thank you page of the petition. Be careful that it is used only when someone has signed the petition. The pixel is practically invisible. The html code to put it is:

<iframe src="http://localhost/count?id=<counter_name>" width="1" height="1" frameborder=0 style="overflow:hidden;" scrolling="no"></iframe>

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