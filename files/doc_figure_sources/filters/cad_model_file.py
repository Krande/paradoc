from files.doc_figure_sources import CADModelFile
import ada


def cad_model_file(cad_model: CADModelFile) -> bytes:
    """This takes in a CAD model filepath and returns image bytes"""
    fp = cad_model.source_inp

    if fp.suffix in [".step", ".stp"]:
        a = ada.from_step(fp)
    else:
        raise NotImplementedError(f"Unsupported CAD file format: {fp.suffix}")

    image = a.render_offscreen()
    return image.tobytes()