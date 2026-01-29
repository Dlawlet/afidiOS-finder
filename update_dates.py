"""Update all dates from Feb 1-2 to Jan 29, 2026"""
import json
import os
from datetime import datetime, timedelta

def update_date(date_str):
    """Convert 2026-02-01 or 2026-02-02 to 2026-01-29"""
    if not date_str or not isinstance(date_str, str):
        return date_str
    
    try:
        # Parse the date
        if 'T' in date_str:
            dt = datetime.fromisoformat(date_str)
        else:
            dt = datetime.strptime(date_str.split('.')[0], '%Y-%m-%d %H:%M:%S')
        
        # If it's Feb 1 or 2, change to Jan 29
        if dt.year == 2026 and dt.month == 2 and dt.day in [1, 2]:
            dt = dt.replace(month=1, day=29)
        
        # Return in original format
        if 'T' in date_str:
            return dt.isoformat()
        elif '.' in date_str:
            return dt.strftime('%Y-%m-%d %H:%M:%S') + '.' + date_str.split('.')[-1]
        else:
            return dt.strftime('%Y-%m-%d %H:%M:%S')
    except:
        return date_str

def update_json_file(filepath):
    """Update all dates in a JSON file"""
    print(f"Updating {filepath}...")
    
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    def update_recursive(obj):
        if isinstance(obj, dict):
            for key, value in obj.items():
                if isinstance(value, str) and ('2026-02-0' in value):
                    obj[key] = update_date(value)
                elif isinstance(value, (dict, list)):
                    update_recursive(value)
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                if isinstance(item, str) and ('2026-02-0' in item):
                    obj[i] = update_date(item)
                elif isinstance(item, (dict, list)):
                    update_recursive(item)
    
    update_recursive(data)
    
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    
    print(f"✅ Updated {filepath}")

# Update all JSON files in exports/
for filename in os.listdir('exports'):
    if filename.endswith('.json'):
        filepath = os.path.join('exports', filename)
        update_json_file(filepath)

print("\n✅ All dates updated from Feb 1-2 to Jan 29, 2026")
