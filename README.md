1. Pip Install all the following in requirements.txt
2. Setup you own gemini api key in .env file
3. put your huggingface account in 'login()' in tools.py and pdfloader.py file
4. Setup you own Gmail Json file (https://console.cloud.google.com/) and then put into the same folder with the code.
5. put the json file name into this code in gmailapi.py file:
    flow = InstalledAppFlow.from_client_secrets_file(
                    "YOURJSONFILENAME", SCOPES
                )

6. Also, the recipient of the Gmail should be updated in the update_order and cancel_order functions in the tools.py file
    sender = "123@gmail.com"
        to = "123@gmail.com"