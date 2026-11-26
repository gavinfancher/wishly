wishly v3


wishly should be a completely self contianed app in a contianer. i would like it to be an api that can work with the current front end. it should communicate with the postgres database. it should recieve calls from api.wishly.dev (proxies thru cloudflare tunnel). it should gets its secrets thru infisical. it should send emails at 9am eastern. it should be plain text thru the resend app. the auth should be the same that it is now. only 88 char min. no resets. lambda should ping it every 1 min and if it detects it is down for 5 mins then send a push notifcaiton thru wihsly that it is down so i can investigate when i want. it should do that thru a approved key over the api.wishly.dev on an endpoint that is rate limited and all that. 

eventually wishly will be deployed on my local k8s cluster that has argocd on it. we will want to make changes to the app. push to gh, gh will build the contianer, argo will detect it and hte updgae teh cluster. that will be the cicd.


