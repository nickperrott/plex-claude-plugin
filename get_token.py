#!/usr/bin/env python3
"""
Simple script to get your Plex authentication token
"""
import getpass
import requests
import json

def get_plex_token():
    print("Plex Token Retrieval")
    print("=" * 50)
    username = input("Enter your Plex username or email: ")
    password = getpass.getpass("Enter your Plex password: ")

    print("\nAuthenticating with Plex...")

    try:
        response = requests.post(
            'https://plex.tv/users/sign_in.json',
            headers={
                'Content-Type': 'application/x-www-form-urlencoded',
                'X-Plex-Client-Identifier': 'plex-mcp-config',
                'X-Plex-Product': 'Plex MCP Server',
                'X-Plex-Version': '1.0'
            },
            data={
                'user[login]': username,
                'user[password]': password
            }
        )

        if response.status_code == 201:
            data = response.json()
            token = data['user']['authToken']
            print("\n✓ Success! Your Plex token is:")
            print(f"\n{token}\n")
            print("Copy this token and update your .env file:")
            print(f"PLEX_TOKEN={token}")
            return token
        else:
            print(f"\n✗ Authentication failed: {response.status_code}")
            print(response.text)
            return None

    except Exception as e:
        print(f"\n✗ Error: {e}")
        return None

if __name__ == "__main__":
    get_plex_token()
