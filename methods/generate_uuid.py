import uuid

def generate_uuid(string):
    """
    Generate a UUID based on the input string.

    :param string: The string to base the UUID on.
    :return: A UUID string.
    """
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, string))