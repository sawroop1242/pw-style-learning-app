"""The one endpoint an editor uses to put a file into storage.

It lives next to the staff viewsets because "may you upload into this batch?" is
the same question as "may you edit this batch?", and the answer comes from the
same ``policy.check_manage``. The storage itself is somebody else's problem
(``objectstore.uploads``).
"""

from __future__ import annotations

from django.core.files.uploadedfile import UploadedFile
from rest_framework import permissions, status
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.response import Response
from rest_framework.views import APIView

from objectstore import uploads
from . import policy
from .models import Course


class StaffAssetUploadView(APIView):
    """``POST /api/staff/uploads/`` — multipart ``file``, ``purpose``, ``course``.

    The bucket is chosen by the course's owner, never by the request, so a main
    admin uploading into a provider's batch writes to that provider's storage.
    """

    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        if not policy.is_staff_role(request.user):
            return Response(
                {"detail": "Only staff may upload course assets."},
                status=status.HTTP_403_FORBIDDEN,
            )

        uploaded = request.FILES.get("file")
        if not isinstance(uploaded, UploadedFile):
            return Response(
                {"file": ["Attach a file."]}, status=status.HTTP_400_BAD_REQUEST
            )

        purpose = str(request.data.get("purpose") or "").strip()
        if purpose not in uploads.PURPOSE_RULES:
            return Response(
                {
                    "purpose": [
                        "Use one of: " + ", ".join(sorted(uploads.PURPOSE_RULES)) + "."
                    ]
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        course_id = request.data.get("course")
        if not course_id:
            return Response(
                {"course": ["Choose the batch this file belongs to."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            course = Course.objects.select_related("owner").get(pk=int(course_id))
        except (Course.DoesNotExist, TypeError, ValueError):
            return Response(
                {"course": ["That batch does not exist."]},
                status=status.HTTP_400_BAD_REQUEST,
            )
        policy.check_manage(
            request.user, course, "You can only upload files into your own batches."
        )

        data = uploaded.read()
        try:
            stored = uploads.store(
                request.user,
                course.owner,
                purpose,
                filename=uploaded.name,
                content_type=uploaded.content_type,
                data=data,
            )
        except uploads.UploadRefused as error:
            return Response(
                {"file": [str(error)]}, status=status.HTTP_400_BAD_REQUEST
            )

        return Response(
            {
                "key": stored.key,
                "url": stored.url,
                "expires_at": stored.expires_at,
                "size": stored.size,
                "content_type": stored.content_type,
                "purpose": purpose,
                "bucket": stored.bucket.name,
            },
            status=status.HTTP_201_CREATED,
        )
