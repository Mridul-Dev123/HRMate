

def open_file(filepath):
    with open(filepath, 'r', encoding='utf-8') as infile:
        return infile.read()


def chunk_file(filepath, chunk_size=1000, chunk_overlap=200):
    text=open_file(filepath)
    i=0
    chunks=[]
    while i<len(text):
        chunk=text[i:i+chunk_size]
        chunks.append(chunk)
        i+=chunk_size-chunk_overlap
    return chunks


