#ifndef UTIL_WRAPPER_H
#define UTIL_WRAPPER_H

#include <BRepTools.hxx>
#include <TopTools_ShapeMapHasher.hxx>
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

    static int shape_map_hasher_hash_code(const TopoDS_Shape& shape) {
        TopTools_ShapeMapHasher hasher;
        return hasher(shape);
    }

    static bool shape_map_hasher_equal(const TopoDS_Shape& a, const TopoDS_Shape& b) {
        TopTools_ShapeMapHasher hasher;
        return hasher(a, b);
    }
};


#endif