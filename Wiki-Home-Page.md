# Greenpeace Service

* ## Service Name 

        A name for the service (Standard across greenpeace org)

    * **Full name**
        * _Full Name_

    * **Short name**
        * _Short Name_

    * **Description** 

        <Two line Description>

    * **SLA**
        * _[Dummy SAL Link](https://en.wikipedia.org/wiki/Service-level_agreement "SLA")_


* ## Service Owner / Committee

    Department / NRO

        <Department / NRO>

    Delegated Contact point / Individual

        Job Title: <Job Title>

        User:   <Name>

        Contact Details

            <Email Address>

    Budget Auth

        <Name>

    Budget Code

        <Greenpeace Budget code>

    Technical Support contact Type

        <3rd party / Global / NRO  / other>

        Greenpeace Technical support start point

            <NRO / FAM / Ops>

    

        3rd Party Contact

            Support Contact

                <name (individual / company)

            Contact Details

                <email / Phone Number>

            Support Details 

                <link>


* ## Devops Team Members

 (list or people)

* ## Backups 

    * Data Restore
        * _[Dummy Data Restore Link](https://en.wikipedia.org/wiki/Data_recovery "Data Restore")_

    * Disaster Recovery
        * _[Dummy Disaster Recovery Link](https://en.wikipedia.org/wiki/Disaster_recovery "Disaster Recovery")_
          
    * Business Continuity
        * _[Dummy Business Continuity Link](https://en.wikipedia.org/wiki/Business_continuity_planning#Business_continuity "Business Continuity")_

* ## Monitoring 
    * Observability
        * _[Dummy Observability Link](https://en.wikipedia.org/wiki/Observability "Observability")_

    * Logging
        * _[Dummy Logging Link](https://en.wikipedia.org/wiki/Log_management "Logging")_

    * Monitoring
      
        * [Test https connectivaty](https://op5.amer.gl3/monitor/index.php/extinfo/details?host=vault.greenpeace.net "Monitoring")

    * Alerting
        * _[Dummy Alerting Link](https://en.wikipedia.org/wiki/Service-level_agreement "Alerting")_

* ## Service components and location

 (links or list)


* ## CI/CD Pipelines
    * Explanation
        * _[Dummy Alerting Link](https://en.wikipedia.org/wiki/Continuous_integration "CI/CD")_
          
    * Release QA test Documents
        * _[Dummy Alerting Link](https://blog.scottlogic.com/2020/02/10/continuous-testing.html "Release QA Tests")_


* ## Documentation
    * End user documentation
        * _[Dummy End user documentation Link](https://www.lawinsider.com/dictionary/end-user-documentation "End user documentation")_

    * Technical Documentation
        * _[Dummy Technical Documentation Link](https://en.wikipedia.org/wiki/Technical_documentation) "Technical Documentation")_


* ## Release Notes
    * Change log in file in Git Repo
        * Name:  _[Dummy Change Log Link](https://en.wikipedia.org/wiki/Changelog "Change Log")_

    * Tag Release (not in gitlab link)
        * _[Dummy Tag Release Link](https://dev.to/neshaz/a-tutorial-for-tagging-releases-in-git-147e "Tag Release")_


# Labels Need

## GCP Labels Restrictions
You can assign up to 64 labels to each resource.
Resources listed as alpha do not yet have support in gcloud or the Google Cloud Console.
Instead, use the Compute Engine API (alpha) to set labels for these resources.

## GCP Label Format
Label keys and values must conform to the following format:
* Keys and values cannot be longer than 63 characters each.
* Keys and values can only contain:
    * Lowercase letters
    * Numeric characters
    * Underscores
    * Hyphens
    * International characters are allowed.
    * Label keys must start with a lowercase letter.
    * Label keys cannot be empty.

| Information                              | GCP Label Key Name | GCP Label Value /Content          | Gitlab Label | Happy Fox Label | Jira Label |
|------------------------------------------|--------------------|-----------------------------------|--------------|-----------------|------------|
| GCP Object ID/Name                       | name               | NA                                | NA | NA | NA |
| What is the service                      | service_name       | ${TF_VAR_label_service_name}      | ${TF_VAR_label_service_name} | ${TF_VAR_label_service_name} | ${TF_VAR_label_service_name} |
| What is the service component            | service_component  | ${TF_VAR_label_service_component} | ${TF_VAR_label_service_component} | ${TF_VAR_label_service_component} | ${TF_VAR_label_service_component} |
| What business function owns this service | service_owner      | ${TF_VAR_label_service_owner}     | NA | NA |  NA|
| Business contact for this service        | business_contact   | ${TF_VAR_label_business_contact}  | NA | NA |  NA|
| Budget code for the service              | budget_code        | ${TF_VAR_label_budget_code}       | NA | NA |  NA|
| Technical Support contact                | tech_contact       | ${TF_VAR_label_tech_contact}      | NA | NA |  NA|
| Release Version Identifier               | release_id         | ${TF_VAR_label_release_id}        | NA | NA |  NA|