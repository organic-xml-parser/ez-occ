%include "std_vector.i"
%include "std_map.i"
%include "std_string.i"
%include "/third_party/pythonocc-core/src/SWIG_files/common/OccHandle.i"

%module(package="util_wrapper") util_wrapper
%feature("flatnested", "1");
%feature("autodoc", "1");
%{
#include <util_wrapper.h>
%}

%template(StringList) std::vector<std::string>;
%template(ShapeList) std::vector<TopoDS_Shape>;


class UtilWrapper {
public:
    static std::string shape_to_string(const TopoDS_Shape& shape);
};
