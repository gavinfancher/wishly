
import requests
import json

response = requests.post(
    'http://100.80.99.58/',
    data=json.dumps({
        'topic': 'test-topic',
        'title': "It's Ethan's birthday today!",
        'message': 'Send Ethan a message 🎉 ',
        'actions': [
            {
                'action': 'view',
                'label': 'Send Message',
                'url': 'sms:+19494499080&body=Happy%20Birthday%20Ethan!!!'
            },
            {
                'action': 'view',
                'label': 'open wishly.dev',
                'url': 'https://fast.com'
            }
        ]
    }),
    headers={'Content-Type': 'application/json'}
)

print(f'Status: {response.status_code}')
print(f'Response: {response.text}')