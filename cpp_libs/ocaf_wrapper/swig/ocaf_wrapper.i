%include "std_vector.i"
%include "std_map.i"
%include "std_string.i"
%include "/third_party/pythonocc-core/src/SWIG_files/common/OccHandle.i"

%module(package="ocaf_wrapper") ocaf_wrapper
%feature("flatnested", "1");
%feature("autodoc", "1");
%{
#include <ocaf_wrapper.h>
%}

%template(StringList) std::vector<std::string>;
%template(ShapeList) std::vector<TopoDS_Shape>;

struct AnnotatedShapeWrapper {
    TopoDS_Shape shape;
    std::string annotationString;
};

%template(AnnotatedShapeWrapperList) std::vector<AnnotatedShapeWrapper>;

class OcafWrapper {
public:
    OcafWrapper(std::string path);

    void setRootShape(const TopoDS_Shape& shape,
                      const std::string& annotation_string);

    AnnotatedShapeWrapper getRootShape();

    void appendShape(const std::string& label,
                     TopoDS_Shape shape,
                     const std::string& annotation_string);

    std::vector<std::string> getShapeNames();

    std::vector<AnnotatedShapeWrapper> getShapesForName(std::string name);

    void setUUID(const std::string& uuid);

    std::string getUUID();

    void save();

    void load();
};
