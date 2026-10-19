import json

path = 'images/image_prompts.json'
m = json.load(open(path))
for it in m['items']:
    it['image_size'] = '1K'
    it['status'] = 'Pending'
    it.pop('last_error', None)
json.dump(m, open(path, 'w'), ensure_ascii=False, indent=2)
print('reset done:', [(i['filename'], i['image_size']) for i in m['items']])
