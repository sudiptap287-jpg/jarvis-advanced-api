def jarvis_integration(self, command):
        """Ye part aapke browser ko aapki backend API se connect karega"""
        import requests
        
        # 1. Local Logic (Instant Offline Response)
        if "system status" in command.lower():
            return "All Systems Nominal. Database Secured."

        # 2. API Integration (Jo aapne Fast API banai hai)
        try:
            api_url = "http://127.0.0.1:8000/v2/get_answer"
            params = {"prompt": command}
            # Yahan apni generate ki hui API key dalein
            headers = {"api_key": "YOUR_GENERATED_KEY_HERE"} 
            
            response = requests.post(api_url, params=params, headers=headers)
            if response.status_code == 200:
                return response.json()['data']
        except:
            return "Connection to Jarvis API failed. Running in standalone mode."
        