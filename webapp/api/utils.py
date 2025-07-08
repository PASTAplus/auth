"""Utility functions for the API."""

import logging
import re

import starlette.responses
import xml.dom.minidom

import util.pretty


log = logging.getLogger(__name__)

#
# Requests
#


async def request_body_to_dict(request):
    """Convert the request body to a dictionary."""
    # is_xml = await is_xml_mimetype(request.headers.get('Accept'))
    # if is_xml:
    #     return _xml_to_dict(request)
    # else:
    return await request.json()


async def is_xml_mimetype(mimetype_str):
    return re.match(r'^\s*(application|text)/xml\s*;?', mimetype_str or '') is not None


async def is_json_mimetype(mimetype_str):
    return re.match(r'^\s*(application|text)/json\s*;?', mimetype_str or '') is not None


# <?xml version="1.0" encoding="UTF-8"?>
# <result>
#   <method>createProfile</method>
#   <msg>An existing profile was used</msg>
#   <edi_id>EDI-8561a27db4254dbfafe4d5bdca3f9db8</edi_id>
# </result>
async def parse_xml(request):
    """Parse the XML request body into a DOM object."""
    body_str = await request.body()
    try:
        dom = xml.dom.minidom.parseString(body_str)
        # Convert the DOM to a dictionary
        dom_dict = {}
        for node in dom.documentElement.childNodes:
            if node.nodeType == node.ELEMENT_NODE:
                dom_dict[node.tagName] = node.firstChild.nodeValue if node.firstChild else ''
        return dom
    except Exception as e:
        log.error(f'Failed to parse XML: {e}')
        raise ValueError('Invalid XML in request body') from e


#
# Responses
#


def get_response_200_ok(request, api_method, msg, **response_dict):
    """Return a '200 OK' response."""
    return _dict_to_response(request, 200, method=api_method, msg=msg, **response_dict)


def get_response_400_bad_request(request, api_method, msg=None, **response_dict):
    """Return a '400 Bad Request' response."""
    return _dict_to_response(
        request,
        400,
        method=api_method,
        msg=msg or 'Bad request: The request was malformed or invalid',
        **response_dict,
    )


def get_response_401_unauthorized(request, api_method, msg=None, **response_dict):
    """Return a '401 Unauthorized' response."""
    return _dict_to_response(
        request,
        401,
        method=api_method,
        msg=msg or 'Unauthorized: Authentication token is missing or invalid',
        **response_dict,
    )


def get_response_403_forbidden(request, api_method, msg=None, **response_dict):
    """Return a '403 Forbidden' response."""
    return _dict_to_response(
        request,
        403,
        method=api_method,
        msg=msg or 'Access denied: Required permissions are missing.',
        **response_dict,
    )


def get_response_404_not_found(request, api_method, msg=None, **response_dict):
    """Return a '404 Not Found' response."""
    return _dict_to_response(
        request,
        404,
        method=api_method,
        msg=msg or 'Not found: The requested item does not exist',
        **response_dict,
    )


def _dict_to_response(request, status_code, **response_dict):
    """Create a JSON or XML response body from a dict.
    The type of the response is determined by the 'Accept' header in the request.
    """
    is_xml = (
        re.match(r'^\s*(application|text)/xml\s*;?', request.headers.get('Accept', '')) is not None
    )
    if is_xml:
        body_str = util.pretty.to_pretty_xml(response_dict)
    else:
        body_str = util.pretty.to_pretty_json(response_dict)
    # log.debug(f'API response: {body_str}')
    return starlette.responses.Response(
        body_str,
        status_code=status_code,
    )
