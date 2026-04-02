#
# Docker image to run sequence to taxonomy analysis
#
# Includes reference data (blastdb)
#
# NEEDS
#   python3
#   Anaconda ? 
#     pandas
#     blast

# Ubunutu base
FROM ubuntu:22.04

# make sure installs dont hang on user input
ENV DEBIAN_FRONTEND=noninteractive


# install r-base and pre-requisitis
# installs R 3.6.3 (on ubuntu:20.04)
RUN set -e \
      && apt-get -y update \
      && apt-get -y dist-upgrade \
      && apt-get -y install --no-install-recommends --no-install-suggests \
        apt-transport-https apt-utils ca-certificates locales pandoc pkg-config \
        ssh rsync \
	ncbi-blast+ \
	python3 \
	python3-pip \
	python3-pandas \
      && apt-get -y autoremove \
      && apt-get clean \
      && rm -rf /var/lib/apt/lists/*

# install python packages
RUN pip install --no-cache-dir biopython
#RUN pip install numpy
#RUN pip install pandas

# install several Python packages with Conda p
#RUN mkdir ./conda
#RUN ./create_conda_env.sh

# UTF-8 mode
RUN set -e \
      && locale-gen en_US.UTF-8 \
      && update-locale

#
# copy in our application
#
# do this as a git clone, instead!?!?
COPY taxablast .
COPY version_git.txt .
# for backward compatibility
COPY seqsearch .

#
# copy in reference data
#
COPY blast/ ./blast/
RUN find ./blast/
# and MATCHING metadata
COPY processed_accessions_b.tsv ./
COPY processed_accessions_b.fa_names.tsv ./
COPY processed_proteins.tsv ./

# 
# test data
#
COPY test_data/nuc/ ./test_data/nuc/
COPY test_out/nuc/ ./test_out/nuc/

# Protein Test Files
COPY test_data/prot/ ./test_data/prot/
COPY test_out/prot/ ./test_out/prot/

# what does ENTRYPOINT do exactly?
# ENTRYPOINT fixed the base command; immutable
# dmd 09/16/25: changed to ENTRYPOINT from CMD to simplify passing arguments.
ENTRYPOINT [ "./taxablast" ]
# CMD add default cmds/arguments
#CMD [ "./taxablast" ]
