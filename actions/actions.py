# This files contains your custom actions which can be used to run
# custom Python code.
#
# See this guide on how to implement these action:
# https://rasa.com/docs/rasa/custom-actions


# This is a simple example for a custom action which utters "Hello World!"

from typing import Any, Text, Dict, List

from rasa_sdk import Action, Tracker
from rasa_sdk.executor import CollectingDispatcher
from rasa_sdk.forms import FormValidationAction
from rasa_sdk.events import SlotSet

class ValidateWoForm(FormValidationAction):
    def name(self) -> Text:
        return "validate_wo_form"

    def slot_mappings(self) -> Dict[Text, Any]:
        # Accept wo_ref_no either as an annotated entity or as raw text reply
        return {
            "wo_ref_no": [
                self.from_entity(entity="wo_ref_no"),
                self.from_text()
            ]
        }

    async def validate_wo_ref_no(
        self,
        value: Text,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any],
    ) -> Dict[Text, Any]:
        # Basic sanitation (trim, reject empty)
        clean = (value or "").strip()
        if not clean:
            dispatcher.utter_message(text="I didn’t catch the reference. Could you type it again?")
            return {"wo_ref_no": None}

        return {"wo_ref_no": clean}


class ActionConfirmWoThenAction(Action):
    def name(self) -> Text:
        return "action_confirm_wo_then_action"

    def run(
        self,
        dispatcher: CollectingDispatcher,
        tracker: Tracker,
        domain: Dict[Text, Any]
    ) -> List[Dict[Text, Any]]:
        wo = tracker.get_slot("wo_ref_no") or ""
        req = tracker.get_slot("required") or "the requested information"
        dispatcher.utter_message(text=f"Got it — work order {wo}. I’ll look for {req} now.")
        # You could trigger business logic here or let your middleware handle it next turn
        return []


class ActionDetails(Action):

    def name(self) -> Text:
        return "action_wo_details"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="details!")

        return []

class ActionFinances(Action):

    def name(self) -> Text:
        return "action_wo_finances"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="finance")

        return []

class ActionPapers(Action):

    def name(self) -> Text:
        return "action_wo_papers"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="papers!")

        return []

class ActionTime(Action):

    def name(self) -> Text:
        return "action_wo_time"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="time")

        return []

class ActionEmployees(Action):

    def name(self) -> Text:
        return "action_wo_employees"

    def run(self, dispatcher: CollectingDispatcher,
            tracker: Tracker,
            domain: Dict[Text, Any]) -> List[Dict[Text, Any]]:

        dispatcher.utter_message(text="employee!")

        return []

