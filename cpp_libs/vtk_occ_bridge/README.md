# VTK OCC Swig bridge

This project provides some bridging between the python bindings
of VTK and OCC. Since VTK uses its own python wrapping scheme it
is not trivial to communicate between them, so the utility to consume
TopoDS_* etc. entities from OCC-python and return the resulting
vtkSmartPointers is located here.