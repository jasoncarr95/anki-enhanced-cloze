import re
from copy import deepcopy
from typing import Optional, Tuple

from aqt import mw
from aqt.gui_hooks import profile_did_open, sync_did_finish
from aqt.utils import askUser

from .constants import MODEL_NAME, NOTE_TYPE_DIR, UPDATE_MSG
from .note_type.model import enhancedModel

try:
    from aqt.models import NotetypeDict
except:
    pass

from .compat import add_compatibility_aliases


def check_note_type(note_type: "NotetypeDict") -> bool:
    """Whether this model is Enhanced cloze version 2.1"""
    return bool(re.search(MODEL_NAME, note_type["name"]))


def new_version_available():
    return current_version() is None or current_version() < incoming_version()


def current_version() -> Optional[Tuple[int]]:
    return version(mw.col.models.by_name(MODEL_NAME))


def incoming_version() -> Optional[Tuple[int]]:
    return version(enhanced_cloze())


def version(note_type: "NotetypeDict") -> Optional[Tuple[int]]:
    front = note_type["tmpls"][0]["qfmt"]
    m = re.match("<!-- VERSION (.+?) -->", front)
    if not m:
        return None

    return tuple(map(int, m.group(1).split(".")))


def set_version(front: str, version: Tuple[int]) -> str:
    return re.sub(
        "<!-- VERSION (.+?) -->",
        f"<!-- VERSION {'.'.join(map(str, version))} -->",
        front,
    )


def add_or_update_model():
    model = mw.col.models.by_name(MODEL_NAME)
    if not model:
        mw.col.models.add(enhanced_cloze())
    else:

        if not new_version_available():
            return

        if current_version() is None:
            update_from_unnamed_version()
            return

        # update the code part, the version number and the config on the front template, keep the rest as it is
        # so that users can customize the other parts of the template
        seperator = "<!-- ENHANCED_CLOZE -->"
        cur_front = model["tmpls"][0]["qfmt"]
        incoming_front = enhanced_cloze()["tmpls"][0]["qfmt"]

        cur_sep_m = re.search(seperator, cur_front)
        incoming_sep_m = re.search(seperator, incoming_front)
        if not cur_sep_m:
            print("Could not find seperator comment, replacing whole front template")
            model["tmpls"][0]["qfmt"] = incoming_front
        else:
            cur_before_sep = cur_front[: cur_sep_m.start()]
            incoming_after_sep = incoming_front[incoming_sep_m.end() :]
            new_front = f"{cur_before_sep}{seperator}{incoming_after_sep}"
            new_front = set_version(new_front, incoming_version())
            new_front = maybe_add_config_option(
                new_front,
                "animateScroll",
                "var animateScroll = true",
                "scrollToClozeOnToggle",
            )
            new_front = maybe_add_config_option(
                new_front,
                "showHintsForPseudoClozes",
                "var showHintsForPseudoClozes = true",
                "animateScroll",
            )
            new_front = maybe_add_config_option(
                new_front,
                "underlineRevealedPseudoClozes",
                "var underlineRevealedPseudoClozes = true",
                "showHintsForPseudoClozes",
            )
            new_front = maybe_add_config_option(
                new_front,
                "underlineRevealedGenuineClozes",
                "var underlineRevealedGenuineClozes = true",
                "underlineRevealedPseudoClozes",
            )
            new_front = maybe_add_config_option(
                new_front,
                "revealPseudoClozesByDefault",
                "var revealPseudoClozesByDefault = false",
                "underlineRevealedGenuineClozes",
            )
            model["tmpls"][0]["qfmt"] = new_front

        mw.col.models.update(model)


def maybe_add_config_option(
    front: str, option_name: str, line_to_be_added: str, previous_option_name: str
) -> str:
    # hacky way to add options to the CONFIG, the CONFIG being the section of the front template
    # before the <!-- CONFIG END --> comment
    # the text in to be added will be added after previous_option where previous_option
    # is the name of a configuration variable

    assert option_name in line_to_be_added

    config_m = re.search("([\w\W]*?)<!-- CONFIG END -->", front)
    config_str = config_m.group(1)

    if option_name in config_str:
        return front

    new_config_str = re.sub(
        f"(?<=\n)(.*)(var +{previous_option_name}.+)\n",
        rf"\1\2\n\1{line_to_be_added}\n",
        config_str,
    )
    result = f"{new_config_str}{front[len(config_str) :]}"
    return result


def update_from_unnamed_version():
    if not askUser(
        title="Enhanced Cloze",
        text=UPDATE_MSG,
        defaultno=True,
    ):
        return

    mm = mw.col.models
    model = mm.by_name(MODEL_NAME)

    def remove_field_if_exists(field_name, model):
        if field_name in mm.field_names(model):
            mm.remove_field(model, mm.field_map(model)[field_name][1])

    fields_to_remove = [f"Cloze{i}" for i in range(1, 51)]
    fields_to_remove.extend(
        [
            "data",
            "In-use Clozes",
        ]
    )

    for field in fields_to_remove:
        remove_field_if_exists(field, model)

    load_enhanced_cloze(model)
    mm.update(model)


def enhanced_cloze() -> "NotetypeDict":
    result = deepcopy(enhancedModel)
    load_enhanced_cloze(result)
    return result


def load_enhanced_cloze(note_type: "NotetypeDict"):
    front_path = NOTE_TYPE_DIR / "Enhanced_Cloze_Front_Side.html"
    css_path = NOTE_TYPE_DIR / "Enhanced_Cloze_CSS.css"
    back_path = NOTE_TYPE_DIR / "Enhanced_Cloze_Back_Side.html"

    with open(front_path) as f:
        front = f.read()
    with open(back_path) as f:
        back = f.read()
    with open(css_path) as f:
        styling = f.read()

    note_type["tmpls"][0]["qfmt"] = front
    note_type["tmpls"][0]["afmt"] = back
    note_type["css"] = styling


def setup_maybe_update_model_on_startup():
    def on_profile_did_open():
        add_compatibility_aliases()

        if not mw.can_auto_sync():
            add_or_update_model()
        else:
            # add the function to the sync_did_finish hook
            # and remove it from the hook after sync
            # so it only gets called on the auto sync on opening Anki
            def fn():
                add_or_update_model()
                sync_did_finish.remove(fn)

            sync_did_finish.append(fn)

    profile_did_open.append(on_profile_did_open)
