"""Model-agnostic classes used to represent the chat state and function calls."""
import abc
import enum
import json
import warnings

from pydantic import BaseModel as PydanticBase, ConfigDict


class BaseModel(PydanticBase, abc.ABC):
    """The base class for all Kani models."""

    def copy_with(self, **new_values):
        """Make a shallow copy of this object, updating the passed attributes (if any) to new values.
        This does not validate the updated attributes!
        This is mostly just a convenience wrapper around ``.model_copy``.
        """
        return self.model_copy(update=new_values)


# ==== chat ====
class ChatRole(enum.Enum):
    """Represents who said a chat message."""

    SYSTEM = "system"
    """The message is from the system (usually a steering prompt)."""

    USER = "user"
    """The message is from the user."""

    ASSISTANT = "assistant"
    """The message is from the language model."""

    FUNCTION = "function"
    """The message is the result of a function call."""


class FunctionCall(BaseModel):
    """Represents a model's request to call a function."""

    model_config = ConfigDict(frozen=True)

    name: str
    """The name of the requested function."""

    arguments: str
    """The arguments to call it with, encoded in JSON."""

    @property
    def kwargs(self) -> dict:
        """The arguments to call the function with, with JSON decoded to a Python dict."""
        return json.loads(self.arguments)

    @classmethod
    def with_args(cls, name: str, **kwargs):
        """Create a function call with the given arguments (e.g. for few-shot prompting)."""
        return cls(name=name, arguments=json.dumps(kwargs))


# --- messages ---
class MessagePart(BaseModel):
    """Part of a message.
    Inherit from this class to tag substrings with metadata or provide multimodality to an engine.
    By default, if coerced to a string, will raise a warning noting that rich message part data was lost.
    """

    def __str__(self):
        """
        Used to define the fallback behaviour when a part is serialized to a string (e.g. via
        :attr:`.ChatMessage.text` ).
        Override this to specify the canonical string representation of your message part.

        Engines that support message parts should generally not use this, preferring to iterate over
        :attr:`.ChatMessage.parts` instead.
        """
        type_name = type(self).__name__
        warnings.warn(
            f"Message part of type {type_name!r} was coerced into a string. Rich data may not be visible to the"
            " user/model.\nDevelopers: If this warning is incorrect, please add support for this message part in your"
            f" engine or override `{type_name}.__str__()`."
        )
        return f"<{type_name} {super().__str__()}>"


class ChatMessage(BaseModel):
    """Represents a message in the chat context."""

    model_config = ConfigDict(frozen=True)

    role: ChatRole
    """Who said the message?"""

    content: str | list[MessagePart | str] | None
    """The data used to create this message. Generally, you should use :attr:`text` or :attr:`parts` instead."""

    @property
    def text(self) -> str | None:
        """The content of the message, as a string.
        Can be None only if the message is a requested function call from the assistant.
        If the message is comprised of multiple parts, concatenates the parts.
        """
        content = self.content
        if content is None:
            return None
        elif isinstance(content, str):
            return content
        return "".join(map(str, content))

    @property
    def parts(self) -> list[MessagePart | str]:
        """The parts of the message that make up its content.
        Can be an empty list only if the message is a requested function call from the assistant.
        """
        content = self.content
        if content is None:
            return []
        elif isinstance(content, str):
            return [content]
        return content

    name: str | None = None
    """The name of the user who sent the message, if set (user/function messages only)."""

    function_call: FunctionCall | None = None
    """The function requested by the model (assistant messages only)."""

    @classmethod
    def system(cls, content: str | list[MessagePart | str], **kwargs):
        """Create a new system message."""
        return cls(role=ChatRole.SYSTEM, content=content, **kwargs)

    @classmethod
    def user(cls, content: str | list[MessagePart | str], **kwargs):
        """Create a new user message."""
        return cls(role=ChatRole.USER, content=content, **kwargs)

    @classmethod
    def assistant(cls, content: str | list[MessagePart | str] | None, **kwargs):
        """Create a new assistant message."""
        return cls(role=ChatRole.ASSISTANT, content=content, **kwargs)

    @classmethod
    def function(cls, name: str, content: str | list[MessagePart | str], **kwargs):
        """Create a new function message."""
        return cls(role=ChatRole.FUNCTION, content=content, name=name, **kwargs)

    def copy_with(self, **new_values):
        # override the copy helper to ensure that setting either text or parts works
        if "text" in new_values:
            if "content" in new_values:
                raise ValueError("At most one of ('content', 'text', 'parts') can be set.")
            new_values["content"] = new_values.pop("text")
        if "parts" in new_values:
            if "content" in new_values:
                raise ValueError("At most one of ('content', 'text', 'parts') can be set.")
            new_values["content"] = new_values.pop("parts")
        return super().copy_with(**new_values)
