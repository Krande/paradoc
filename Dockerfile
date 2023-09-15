FROM mambaorg/micromamba:1.5-bullseye

WORKDIR /app
COPY ./git-doc/environment.yml ./git-doc/environment.yml

RUN micromamba env create -f git-doc/environment.yml -y

# Make RUN commands use the new environment:
SHELL ["micromamba", "run", "-n", "git-doc", "/bin/bash", "-c"]

COPY . .

# start a production server for fastapi app from the micromamba env git-doc
CMD ["micromamba", "run", "-n", "git-doc", "/bin/bash", "-c", "uvicorn", "git-doc.src.git_doc.main:app", "--host", "0.0.0.0", "--port", "8000"]