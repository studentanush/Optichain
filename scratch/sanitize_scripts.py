import sys

def sanitize(path):
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace common problematic characters
    content = content.replace('\u2192', '->')
    content = content.replace('\u2500', '-')
    content = content.replace('\u2705', '[ok]')
    content = content.replace('\ud83d\udcca', '[chart]')
    content = content.replace('\u2699\ufe0f', '[step]')
    content = content.replace('\u26a0\ufe0f', '[!]')
    content = content.replace('\u23f1\ufe0f', '[time]')
    content = content.replace('\u2b50', '*')
    
    # Strip any remaining non-ASCII
    sanitized = content.encode('ascii', 'ignore').decode('ascii')
    
    with open(path, 'w', encoding='ascii') as f:
        f.write(sanitized)

if __name__ == "__main__":
    for arg in sys.argv[1:]:
        sanitize(arg)
