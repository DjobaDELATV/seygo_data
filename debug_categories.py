import requests
import json

def check_cat_detailed(cat_name):
    url = "https://yugipedia.com/api.php"
    headers = {"User-Agent": "YGOJSON-Debug/1.0"}
    
    # Test 1: Default query
    params = {
        "action": "query",
        "list": "categorymembers",
        "cmtitle": cat_name,
        "format": "json",
        "cmlimit": 10
    }
    r = requests.get(url, params=params, headers=headers)
    print(f"Test 1 (default): {r.url}")
    try:
        data = r.json()
        count = len(data.get("query", {}).get("categorymembers", []))
        print(f"  -> {count} members")
    except:
        print(f"  -> Error: {r.text[:100]}")
    
    # Test 2: With cmtype
    params["cmtype"] = "page"
    r = requests.get(url, params=params, headers=headers)
    print(f"Test 2 (cmtype=page): {r.url}")
    try:
        data = r.json()
        members = data.get("query", {}).get("categorymembers", [])
        print(f"  -> {len(members)} members")
        if members:
            print(f"  -> First: {members[0].get('title', 'N/A')}")
    except:
        print(f"  -> Error: {r.text[:100]}")

# Test the DL Skills category
check_cat_detailed("Category:Yu-Gi-Oh! Duel Links Skills")
check_cat_detailed("Category:Skill Cards")
