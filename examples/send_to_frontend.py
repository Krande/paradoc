import paradoc as pa

def main():
    od = pa.OneDoc("../files/doc1")
    od.send_to_frontend()

if __name__ == '__main__':
    main()