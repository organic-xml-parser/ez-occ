#ifndef OCAF_WRAPPER_H
#define OCAF_WRAPPER_H

#include <Poly_PolygonOnTriangulation.hxx>
#include <Poly_Triangulation.hxx>
#include <TDocStd_Document.hxx>
#include <TDocStd_Application.hxx>
#include <TDF_Data.hxx>
#include <XCAFApp_Application.hxx>
#include <PCDM_ReaderStatus.hxx>
#include <PCDM_StoreStatus.hxx>
#include <BinDrivers.hxx>
#include <TDataStd_Integer.hxx>
#include <TDataStd_Name.hxx>
#include <TDataStd_Comment.hxx>
#include <TDataStd_ExtStringArray.hxx>
#include <TCollection_ExtendedString.hxx>
#include <TNaming_Builder.hxx>
#include <TNaming_NamedShape.hxx>
#include <BRepPrimAPI_MakeBox.hxx>
#include <TDF_ChildIterator.hxx>
#include <string>
#include <sstream>
#include <map>
#include <stdexcept>
#include <iostream>
#include <optional>


struct AnnotatedShapeWrapper {
    TopoDS_Shape shape;
    std::string annotationString;
};

class OcafWrapper {
private:
    std::map<std::string, std::vector<AnnotatedShapeWrapper>> shapes;

    std::optional<AnnotatedShapeWrapper> rootShape = std::nullopt;

    std::string _path;

    std::optional<std::string> _uuid;

public:

    OcafWrapper(const std::string& path) : _path(path) {
    }

    void setUUID(const std::string& uuid) {
        _uuid = uuid;
    }

    std::string getUUID() {
        if (!_uuid.has_value()) {
            throw std::runtime_error("No UUID has been set");
        }

        return _uuid.value();
    }

    void setRootShape(const TopoDS_Shape& shape, const std::string& annotationString) {
        this->rootShape = AnnotatedShapeWrapper{ shape, annotationString };
    }

    AnnotatedShapeWrapper getRootShape() const {
        if (!rootShape.has_value()) {
            throw std::runtime_error("Root shape not specified.");
        }

        return rootShape.value();
    }

    void appendShape(std::string label, TopoDS_Shape shape, std::string annotationString) {
        if (shapes.find(label) == shapes.end()) {
            shapes[label] = std::vector<AnnotatedShapeWrapper>();
        }

        shapes[label].push_back(AnnotatedShapeWrapper{ shape, annotationString });
    }

    /**
     * Safest option: return a copy of the map.
     **/
    std::vector<std::string> getShapeNames() const {
        std::vector<std::string> result;
        for (const auto& item : shapes) {
            result.push_back(item.first);
        }

        return result;
    }

    std::vector<AnnotatedShapeWrapper> getShapesForName(const std::string& name) const {
        if (shapes.find(name) == shapes.end()) {
            throw std::runtime_error("Specified name is not present");
        }

        std::vector<AnnotatedShapeWrapper> result;

        for (const auto& s : shapes.at(name)) {
            result.push_back(s);
        }

        return result;
    }

    static std::string formatPCDMStoreStatus(const PCDM_StoreStatus& status) {
        switch (status) {
        case PCDM_SS_OK:
            return "PCDM_SS_OK";
        case PCDM_SS_DriverFailure:
            return "PCDM_SS_DriverFailure";
        case PCDM_SS_WriteFailure:
            return "PCDM_SS_WriteFailure";
        case PCDM_SS_Failure:
            return "PCDM_SS_Failure";
        case PCDM_SS_Doc_IsNull:
            return "PCDM_SS_Doc_IsNull";
        case PCDM_SS_No_Obj:
            return "PCDM_SS_No_Obj";
        case PCDM_SS_Info_Section_Error:
            return "PCDM_SS_Info_Section_Error";
        case PCDM_SS_UserBreak:
            return "PCDM_SS_UserBreak";
        }

        return "unknown";
    }

    static std::string formatPCDMReaderStatus(const PCDM_ReaderStatus& status) {
        switch (status) {
        case PCDM_RS_OK:
            return "PCDM_RS_OK";
        case PCDM_RS_NoDriver:
            return "PCDM_RS_NoDriver";
        case PCDM_RS_UnknownFileDriver:
            return "PCDM_RS_UnknownFileDriver";
        case PCDM_RS_OpenError:
            return "PCDM_RS_OpenError";
        case PCDM_RS_NoVersion:
            return "PCDM_RS_NoVersion";
        case PCDM_RS_NoSchema:
            return "PCDM_RS_NoSchema";
        case PCDM_RS_NoDocument:
            return "PCDM_RS_NoDocument";
        case PCDM_RS_ExtensionFailure:
            return "PCDM_RS_ExtensionFailure";
        case PCDM_RS_WrongStreamMode:
            return "PCDM_RS_WrongStreamMode";
        case PCDM_RS_FormatFailure:
            return "PCDM_RS_FormatFailure";
        case PCDM_RS_TypeFailure:
            return "PCDM_RS_TypeFailure";
        case PCDM_RS_TypeNotFoundInSchema:
            return "PCDM_RS_TypeNotFoundInSchema";
        case PCDM_RS_UnrecognizedFileFormat:
            return "PCDM_RS_UnrecognizedFileFormat";
        case PCDM_RS_MakeFailure:
            return "PCDM_RS_MakeFailure";
        case PCDM_RS_PermissionDenied:
            return "PCDM_RS_PermissionDenied";
        case PCDM_RS_DriverFailure:
            return "PCDM_RS_DriverFailure";
        case PCDM_RS_AlreadyRetrievedAndModified:
            return "PCDM_RS_AlreadyRetrievedAndModified";
        case PCDM_RS_AlreadyRetrieved:
            return "PCDM_RS_AlreadyRetrieved";
        case PCDM_RS_UnknownDocument:
            return "PCDM_RS_UnknownDocument";
        case PCDM_RS_WrongResource:
            return "PCDM_RS_WrongResource";
        case PCDM_RS_ReaderException:
            return "PCDM_RS_ReaderException";
        case PCDM_RS_NoModel:
            return "PCDM_RS_NoModel";
        case PCDM_RS_UserBreak:
            return "PCDM_RS_UserBreak";
        }

        return "unknown";
    }

    void load() {
        //std::cout << "LOADING SHAPE..." << std::endl;

        Handle(TDocStd_Application) app = new TDocStd_Application();
        BinDrivers::DefineFormat(app);
        Handle(TDocStd_Document) doc;
        auto readStatus = app->Open(_path.c_str(), doc);

        if (readStatus != PCDM_RS_OK) {
            throw std::runtime_error((std::stringstream() << "Document read failure: " << formatPCDMReaderStatus(readStatus)).str());
        }

        auto mainLabel = doc->Main();
        //printLabels(mainLabel);
        auto rootShapeArray = OcafWrapper::getExtStringArray(mainLabel);
        if (rootShapeArray->size() != 2) {
            throw std::runtime_error("Root shape string array incorrect");
        }

        setRootShape(OcafWrapper::getShape(mainLabel), rootShapeArray->at(1));
        this->_uuid = rootShapeArray->at(0);

        // iterate through main label children
        TDF_ChildIterator iterator(mainLabel, false);
        while (iterator.More()) {
            //std::cout << "Loading from main label" << std::endl;
            auto child = iterator.Value();
            Handle(TDataStd_Name) name;
            if (!child.FindAttribute(TDataStd_Name::GetID(), name)) {
                throw std::runtime_error("could not retrieve label name");
            }

            for (int i = 0; i < child.NbChildren(); i++) {
                TDF_Label indexedShapeLabel = child.FindChild(i, false);

                Handle(TNaming_NamedShape) namedShape;
                if (!indexedShapeLabel.FindAttribute(TNaming_NamedShape::GetID(), namedShape)) {
                    throw std::runtime_error("Could not retrieve named shape");
                }

                auto annotationStringArr = getExtStringArray(indexedShapeLabel);
                if (annotationStringArr->size() != 1) {
                    throw std::runtime_error("Annotation string could not be found!");
                }

                appendShape((std::stringstream() << name->Get()).str(), namedShape->Get(), annotationStringArr->at(0));
            }

            iterator.Next();
        }

        //printLabels(main);
    }

    void save() {
        if (!rootShape.has_value()) {
            throw std::runtime_error("root shape has not been specified.");
        }

        Handle(TDocStd_Application) app = new TDocStd_Application();
        BinDrivers::DefineFormat(app);
        Handle(TDocStd_Document) doc;
        app->NewDocument("BinOcaf",doc);

        if (doc.IsNull()) {
            throw std::runtime_error("Fail: could not create OCAF document");
        }

        TDF_Label mainLabel = doc->Main();
        TDataStd_Name::Set(mainLabel, "DOCUMENT ROOT");

        if (!_uuid.has_value()) {
            throw std::runtime_error("UUID not set");
        }

        std::vector<std::string> mainArray;
        mainArray.push_back(_uuid.value());
        mainArray.push_back(rootShape.value().annotationString);
        setExtStringArray(mainLabel, mainArray);
        TNaming_Builder(mainLabel).Generated(rootShape.value().shape);

        for (const auto& entry : shapes) {
            //std::cout << "Serializing shape names: " << entry.first << std::endl;

            TDF_Label shapeListLabel = mainLabel.NewChild();
            TDataStd_Name::Set(shapeListLabel, entry.first.c_str());

            for (int i = 0; i < entry.second.size(); i++) {
                //std::cout << "    Serializing index " << i << std::endl;

                // create a child element for each shape in the collection.
                TDF_Label indexedShapeLabel = shapeListLabel.FindChild(i, true);
                std::vector<std::string> annotationString;
                annotationString.push_back(entry.second[i].annotationString);
                setExtStringArray(indexedShapeLabel, annotationString);
                TNaming_Builder(indexedShapeLabel).Generated(entry.second[i].shape);
            }
        }

        auto storeStatus = app->SaveAs(doc, _path.c_str());
        //std::cout << "Store status: " << formatPCDMStoreStatus(storeStatus) << std::endl;
        if (storeStatus != PCDM_SS_OK) {
            //std::cout << "Data store failed!" << std::endl;
            throw std::runtime_error("OCAF PCDM data store failed.");
        }

        app->Close(doc);

        //std::cout << "Success" << std::endl;
    }

private:
    static void setExtStringArray(const TDF_Label& label, const std::vector<std::string>& values) {
        Handle(TDataStd_ExtStringArray) array = TDataStd_ExtStringArray::Set(
            label,
            TDataStd_ExtStringArray::GetID(),
            0,
            values.size() - 1);

        for (int i = 0; i < values.size(); i++) {
            array->SetValue(i, values[i].c_str());
        }
    }

    static std::unique_ptr<std::vector<std::string>> getExtStringArray(const TDF_Label& label) {
        Handle(TDataStd_ExtStringArray) arr;
        if (!label.FindAttribute(TDataStd_ExtStringArray::GetID(), arr)) {
            throw std::runtime_error("Could not fetch string array");
        }

        auto result = std::make_unique<std::vector<std::string>>();

        for (int i = 0; i < arr->Length(); i++) {
            result->push_back(extended_string_tostdstring(arr->Value(i)));
        }

        return std::move(result);
    }

    static TopoDS_Shape getShape(const TDF_Label& label) {
        Handle(TNaming_NamedShape) namedShape;

        if (!label.FindAttribute(TNaming_NamedShape::GetID(), namedShape)) {
            throw std::runtime_error("Could not find named shape associated with label");
        }

        return namedShape->Get();
    }

    static std::string extended_string_tostdstring(const TCollection_ExtendedString& extended_string) {
        std::string result(extended_string.Length(), ' ');

        for (int i = 0; i < extended_string.Length(); i++) {
            result[i] = extended_string.Value(i + 1);
        }

        return result;
    }

    static void printLabels(TDF_Label& label, std::string prefix="") {
        Handle(TDataStd_Name) name;

        const int numChildren = label.NbChildren();

        if (label.FindAttribute(TDataStd_Name::GetID(), name)) {
            std::cout << prefix << "LABEL (" << name->Get() << ") ";
        } else {
            std::cout << prefix << "Label unnamed ";
        }

        std::cout << " (tag " << label.Tag() << ") ";
        std::cout << numChildren << " children" << std::endl;

        TDF_ChildIterator iterator(label, false);
        while (iterator.More()) {
            auto child = iterator.Value();

            std::stringstream ss;
            ss << prefix << "    ";


            if (child.IsNull()) {
                std::cout << ss.str() << "NULL" << std::endl;
            } else {
                printLabels(child, ss.str());
            }

            iterator.Next();
        }


    }

};


#endif