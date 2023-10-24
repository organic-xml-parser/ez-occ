from ezocc.cad.gui.pyqt.widgets.widgets import WidgetToolFactory, WidgetTool
from ezocc.cad.model.session import Session


class ScaleWidgetToolFactory(WidgetToolFactory):

    def name(self) -> str:
        return "Scale"

    def can_create(self) -> bool:
        if session.workspace is None:
            return False

        selected_parts = session.workspace.selected_parts

        return len(selected_parts) == 1

    def create(self) -> WidgetTool:
        raise NotImplementedError()
