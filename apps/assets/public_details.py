from .operator_review import get_public_operator_details


def public_contact_details(asset, operator_details=None):
    details = (get_public_operator_details(asset) if operator_details is None else operator_details)
    fields = ("text", "email", "phone", "url")
    supplied = any(details.get(f"contact_{field}") for field in fields)
    return {
        "operator_provided": supplied,
        **{field: details.get(f"contact_{field}", "") if supplied
           else getattr(asset, f"contact_{field}") for field in fields},
    }
