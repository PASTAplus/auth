import uuid


def get_new_edi_id():
    return f'EDI-{uuid.uuid4().hex}'
