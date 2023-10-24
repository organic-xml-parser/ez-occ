FROM ubuntu:22.04

ARG THIRDPARTY_BUILD_TYPE=Release

RUN apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y wget libxmu-dev vim gdb libglu1-mesa-dev libgl1-mesa-dev libxmu-dev libxi-dev build-essential cmake libfreetype6-dev tk-dev python3-dev rapidjson-dev python3 git python3-pip libpcre2-dev
RUN DEBIAN_FRONTEND=noninteractive apt-get install tk tcl tk-dev tcl-dev libx11-dev libxt-dev rapidjson-dev -y
RUN pip3 install svgwrite numpy matplotlib PyQt5
RUN pip3 install setuptools~=59.6.0
RUN pip3 install aqtinstall~=3.0.2

ARG QT=5.15.2
ARG QT_MODULES=all
ARG QT_HOST=linux
ARG QT_TARGET=desktop
ARG QT_ARCH=""
RUN aqt install --outputdir /opt/qt ${QT} ${QT_HOST} ${QT_TARGET} ${QT_ARCH} -m ${QT_MODULES}
ENV PATH /opt/qt/${QT}/gcc_64/bin:$PATH
ENV QT_PLUGIN_PATH /opt/qt/${QT}/gcc_64/plugins/
ENV QML_IMPORT_PATH /opt/qt/${QT}/gcc_64/qml/
ENV QML2_IMPORT_PATH /opt/qt/${QT}/gcc_64/qml/

# seems that this needed to be installed to get pyqt to work
COPY ./requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt
RUN pip3 install PyQt5==5.15.4
RUN apt-get install libqt5gui5 -y

RUN mkdir /third_party
WORKDIR /third_party

# VTK
RUN git clone --depth 1 --branch v9.1.0 https://github.com/Kitware/VTK.git
WORKDIR ./VTK
# replace AllValues with vtkAllValues in vtk source due to collision with OCCT
RUN find . -type f -exec sed -i 's/AllValues/vtkAllValues/g' {} +
RUN git status
RUN mkdir build
WORKDIR ./build
RUN mkdir -p -m 0700 /run/user/0
ENV XDG_RUNTIME_DIR=/run/user/0
RUN cmake .. \
    -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE \
    -DVTK_ENABLE_WRAPPING=ON \
    -DVTK_WRAP_PYTHON=ON \
    -DVTK_BUILD_EXAMPLES=ON \
    -DVTK_GROUP_ENABLE_Imaging=WANT \
    -DVTK_GROUP_ENABLE_MPI=WANT \
    -DVTK_GROUP_ENABLE_Qt=WANT \
    -DVTK_GROUP_ENABLE_Rendering=WANT \
    -DVTK_GROUP_ENABLE_StandAlone=WANT \
    -DVTK_GROUP_ENABLE_Views=WANT \
    -DVTK_GROUP_ENABLE_Web=WANT \
    -DBUILD_SHARED_LIBS=ON

RUN git status
RUN make -j6
RUN make install

# VTK: python wrapping component
WORKDIR ./Wrapping/Python
RUN make -j6
RUN make install
ENV LD_LIBRARY_PATH=/third_party/VTK/build/lib:${LD_LIBRARY_PATH}
ENV PYTHONPATH=/third_party/VTK/build/lib/python3.10/site-packages:${PYTHONPATH}
RUN apt-get install vim -y
RUN apt-get install gdb -y
WORKDIR ../..

# SWIG
WORKDIR /third_party
RUN wget http://prdownloads.sourceforge.net/swig/swig-4.1.1.tar.gz
RUN tar -zxvf swig-4.1.1.tar.gz
WORKDIR ./swig-4.1.1
RUN ./configure && make -j4 && make install

# OPENCASCADE
WORKDIR /third_party
RUN wget -O occt-7.7.2.tgz "https://git.dev.opencascade.org/gitweb/?p=occt.git;a=snapshot;h=cec1ecd0c9f3b3d2572c47035d11949e8dfa85e2;sf=tgz"
RUN tar -zxvf occt-7.7.2.tgz
WORKDIR /third_party/occt-cec1ecd
WORKDIR ./build
RUN cmake .. \
    -DUSE_VTK=ON  \
    -D3RDPARTY_VTK_INCLUDE_DIR=/usr/local/include/vtk-9.1/ \
    -D3RDPARTY_TCL_INCLUDE_DIR=/usr/include/tcl8.6 \
    -D3RDPARTY_TK_INCLUDE_DIR=/usr/include/tcl8.6 \
    -DBUILD_RELEASE_DISABLE_EXCEPTIONS=OFF \
    -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE \
    -DUSE_RAPIDJSON=ON
RUN make -j6
RUN make install
RUN ldconfig

# pythonocc
WORKDIR /third_party
RUN git clone --depth 1 --branch 7.7.2 https://github.com/tpaviot/pythonocc-core
WORKDIR ./pythonocc-core
RUN mkdir build
WORKDIR ./build
RUN cmake .. \
 -DPYTHONOCC_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE \
 -DPYTHONOCC_MESHDS_NUMPY=ON
RUN make -j6
RUN make install

# not sure why this is now needed manually...
ENV PYTHONPATH=/usr/local/lib/python3/dist-packages:${PYTHONPATH}

RUN mkdir /wsp
WORKDIR /wsp

RUN touch $HOME/.Xauthority
RUN apt-get install xauth -y

RUN apt-get install bash -y

# seems that this needed to be installed to get pyqt to work
COPY ./requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt

COPY ./cpp_libs /cpp_libs

WORKDIR /cpp_libs/util_wrapper
RUN mkdir -p build && cd build && rm -rf ./* && cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE && make install

WORKDIR /cpp_libs/vtk_occ_bridge
RUN mkdir -p build && cd build && rm -rf ./* && cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE && make install

WORKDIR /cpp_libs/ocaf_wrapper
RUN mkdir -p build && cd build && rm -rf ./* && cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE && make install

WORKDIR /wsp

RUN echo '#!/bin/bash' > /entrypoint.sh
RUN echo 'xauth add $DISPLAY $XAUTH_ADD_ARG' >> /entrypoint.sh
RUN echo 'pip3 install -e .' >> /entrypoint.sh
RUN echo 'exec $@' >> /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN cat /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["/bin/bash"]
