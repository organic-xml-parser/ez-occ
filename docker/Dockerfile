FROM ubuntu:22.04

RUN apt-get update
RUN apt-get install python3.10-dev git cmake -y

# needed for solvespace
RUN apt-get install git build-essential cmake zlib1g-dev libpng-dev \
            libcairo2-dev libfreetype6-dev libjson-c-dev \
            libfontconfig1-dev libgtkmm-3.0-dev libpangomm-1.4-dev \
            libgl-dev libglu-dev libspnav-dev -y

RUN mkdir /third_party
WORKDIR /third_party

# copy vtk and opencascade sources
RUN git clone --depth 1 --branch V7_5_1 https://github.com/Open-Cascade-SAS/OCCT.git
RUN git clone --depth 1 --branch 7.5.1 https://github.com/tpaviot/pythonocc-core
RUN git clone --depth 1 --branch v9.1.0 https://github.com/Kitware/VTK.git

RUN git clone --depth 1 --branch v3.1 https://github.com/solvespace/solvespace
WORKDIR /third_party/solvespace
RUN git submodule update --init --recursive
WORKDIR /third_party

# build order
# solvespace
# vtk
# OCCT
# python-OCCT

RUN apt-get install python3-pip -y
RUN pip3 install --upgrade pip

ARG THIRDPARTY_BUILD_TYPE=Release

WORKDIR /third_party/solvespace
RUN mkdir build
WORKDIR ./build
RUN cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE -DENABLE_OPENMP=ON
RUN make
RUN make install

WORKDIR /third_party/VTK
RUN pip3 install setuptools~=59.6.0
RUN pip3 install aqtinstall~=3.0.2

# taken from aqtinstall github example Dockerfile
ARG QT=5.15.2
ARG QT_MODULES=all
ARG QT_HOST=linux
ARG QT_TARGET=desktop
ARG QT_ARCH=
RUN aqt install --outputdir /opt/qt ${QT} ${QT_HOST} ${QT_TARGET} ${QT_ARCH} -m ${QT_MODULES}
ENV PATH /opt/qt/${QT}/gcc_64/bin:$PATH
ENV QT_PLUGIN_PATH /opt/qt/${QT}/gcc_64/plugins/
ENV QML_IMPORT_PATH /opt/qt/${QT}/gcc_64/qml/
ENV QML2_IMPORT_PATH /opt/qt/${QT}/gcc_64/qml/


RUN mkdir -p -m 0700 /run/user/0
# replace AllValues with vtkAllValues in vtk source due to collision with OCCT
RUN find . -type f -exec sed -i 's/AllValues/vtkAllValues/g' {} +
RUN git status
RUN mkdir build
WORKDIR ./build

RUN DEBIAN_FRONTEND=noninteractive apt-get install tk tcl -y
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
WORKDIR ./Wrapping/Python
RUN make -j6
RUN make install
ENV LD_LIBRARY_PATH=/third_party/VTK/build/lib:${LD_LIBRARY_PATH}
ENV PYTHONPATH=/third_party/VTK/build/lib/python3.10/site-packages:${PYTHONPATH}
RUN apt-get install vim -y
RUN apt-get install gdb -y
WORKDIR ../..

RUN apt-get install libxmu-dev -y # does not seem to be needed for OCC 7.6.2

WORKDIR /third_party/OCCT
RUN mkdir build
WORKDIR ./build
RUN DEBIAN_FRONTEND=noninteractive apt-get install tk-dev tcl-dev libx11-dev libxt-dev -y
RUN cmake .. \
    -DUSE_VTK=ON -D3RDPARTY_VTK_INCLUDE_DIR=/usr/local/include/vtk-9.1/ \
    -D3RDPARTY_TCL_INCLUDE_DIR=/usr/include/tcl8.6 \
    -D3RDPARTY_TK_INCLUDE_DIR=/usr/include/tcl8.6 \
    -DBUILD_RELEASE_DISABLE_EXCEPTIONS=OFF \
    -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE

RUN make -j6
RUN make install


WORKDIR /third_party/pythonocc-core
RUN apt-get install swig4.0 -y
RUN apt-get install rapidjson-dev -y
RUN mkdir build
WORKDIR ./build
RUN cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE
RUN make -j6
RUN make install

RUN ldconfig

RUN mkdir /wsp
WORKDIR /wsp

RUN touch $HOME/.Xauthority
RUN apt-get install xauth -y

RUN apt-get install bash -y

# seems that this needed to be installed to get pyqt to work
COPY ./requirements.txt /requirements.txt
RUN pip3 install -r /requirements.txt --root-user-action=ignore
RUN pip3 install PyQt5==$QT --root-user-action=ignore
RUN apt-get install libqt5gui5 -y

RUN echo '#!/bin/bash' > /entrypoint.sh
RUN echo 'xauth add $DISPLAY $XAUTH_ADD_ARG' >> /entrypoint.sh
RUN echo 'pip3 install -r requirements.txt' >> /entrypoint.sh
RUN echo 'pip3 install -e .' >> /entrypoint.sh
RUN echo "pushd /wsp/cpp_libs/util_wrapper && mkdir -p build && cd build && rm -rf ./* && cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE && make install && popd" >> /entrypoint.sh
RUN echo "pushd /wsp/cpp_libs/vtk_occ_bridge && mkdir -p build && cd build && rm -rf ./* && cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE && make install && popd" >> /entrypoint.sh
RUN echo "pushd /wsp/cpp_libs/ocaf_wrapper && mkdir -p build && cd build && rm -rf ./* && cmake .. -DCMAKE_BUILD_TYPE=$THIRDPARTY_BUILD_TYPE && make install && popd" >> /entrypoint.sh
RUN echo 'exec $@' >> /entrypoint.sh
RUN chmod +x /entrypoint.sh
RUN cat /entrypoint.sh

ENTRYPOINT [ "/entrypoint.sh" ]
CMD ["/bin/bash"]
