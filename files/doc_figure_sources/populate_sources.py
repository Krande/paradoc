import ada

def create_source_models():
    """Populate the document figure source models directory with basic models using adapy"""
    bm = ada.Beam('bm1', (0,0,0), (10,0,0), 'IPE300')
    a = ada.Assembly() / bm
    a.to_stp('files/cad.stp')

if __name__ == '__main__':
    create_source_models()