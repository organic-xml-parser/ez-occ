#ifndef UTIL_WRAPPER_H
#define UTIL_WRAPPER_H

#include <BRepTools.hxx>
#include <sstream>
#include <map>
#include <stdexcept>
#include <iostream>
#include <optional>

class UtilWrapper {
public:
    static std::string shape_to_string(const TopoDS_Shape& shape) {
        std::stringstream ss;
        BRepTools::Write(shape, ss);
        return ss.str();
    }
};


#endif