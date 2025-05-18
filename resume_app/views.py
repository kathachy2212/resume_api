from rest_framework import generics, status
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView
from .models import Resume, Skill
from .serializers import RegisterSerializer, ResumeSerializer, CustomTokenObtainPairSerializer, SkillSerializer
from docx import Document
import re
import os
from difflib import get_close_matches
from django.contrib.auth import get_user_model

User = get_user_model()

class RegisterView(generics.CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [AllowAny]


class CheckUsernameView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        username = request.query_params.get('username', '').strip()
        if not username:
            return Response({'error': 'Username parameter is required'}, status=status.HTTP_400_BAD_REQUEST)

        exists = User.objects.filter(username__iexact=username).exists()
        return Response({'exists': exists}, status=status.HTTP_200_OK)


class LoginView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer


class SkillListCreateView(generics.ListCreateAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SkillSerializer

    def get_queryset(self):
        return Skill.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SkillUpdateDeleteView(generics.RetrieveUpdateDestroyAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = SkillSerializer

    def get_queryset(self):
        return Skill.objects.filter(user=self.request.user)


class ResumeUploadView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ResumeSerializer(data=request.data)
        if serializer.is_valid():
            resume = serializer.save(user=request.user)
            file_path = resume.file.path
            file_ext = os.path.splitext(file_path)[1].lower()

            if file_ext == ".docx":
                text = self.extract_text_from_docx(file_path)
            elif file_ext == ".pdf":
                text = self.extract_text_from_pdf(file_path)
            else:
                return Response({"error": "Unsupported file type"}, status=400)

            resume.name = self.extract_name(text)
            resume.email = self.extract_email(text)
            resume.skills = self.extract_skills(text, request.user)
            resume.ats_score = self.calculate_ats_score(text, request.user)
            resume.save()

            return Response(ResumeSerializer(resume).data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    def extract_text_from_docx(self, path):
        try:
            from docx.opc.constants import RELATIONSHIP_TYPE as RT
            doc = Document(path)
            full_text = []

            for para in doc.paragraphs:
                full_text.append(para.text)

            # Extract hyperlinks with mailto
            rels = doc.part.rels
            for rel in rels:
                if rels[rel].reltype == RT.HYPERLINK:
                    target = rels[rel]._target
                    if target.startswith("mailto:"):
                        full_text.append(target)

            return "\n".join(full_text)
        except Exception:
            return ""

    def extract_text_from_pdf(self, path):
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(path)
            full_text = []

            for page in doc:
                text = page.get_text()
                full_text.append(text)

                links = page.get_links()
                for link in links:
                    uri = link.get('uri', '')
                    if uri.startswith("mailto:"):
                        full_text.append(uri)

            return "\n".join(full_text)
        except Exception:
            return ""

    def extract_name(self, text):
        lines = text.strip().split('\n')
        for line in lines[:10]:
            line = line.strip()
            if not line or re.search(r'\d|[@:]', line):
                continue
            if re.match(r'^([A-Z]{2,}(?:\s+[A-Z]{2,}){1,2})$', line):
                return line.title()
            if re.match(r"^[A-Z][a-z]+(\s[A-Z][a-z]+)+$", line):
                return line
        return "Unknown"

    def extract_email(self, text):
        # LaTeX format
        email = self.extract_email_from_latex(text)
        if email and email != "unknown@example.com":
            return email

        # mailto: format
        mailto_match = re.search(r'mailto:([a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+)', text)
        if mailto_match:
            return mailto_match.group(1)

        # plain text
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        matches = re.findall(email_pattern, text)
        if matches:
            return matches[0]

        return "unknown@example.com"

    def extract_email_from_latex(self, text):
        cleaned_text = re.sub(r'\\href\{mailto:([^\}]+)\}\{[^\}]*\}', r'\1', text)
        email_pattern = r'[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+'
        match = re.search(email_pattern, cleaned_text)
        return match.group(0) if match else "unknown@example.com"

    def extract_skills(self, text, user):
        known_skills = list(Skill.objects.filter(user=user).values_list('name', flat=True))
        words = set(re.findall(r'\b\w+\b', text.lower()))
        found = []

        for skill in known_skills:
            matches = get_close_matches(skill.lower(), words, cutoff=0.8)
            if matches:
                found.append(skill)

        return ', '.join(found) if found else "Not detected"

    def calculate_ats_score(self, text, user):
        all_skills = list(Skill.objects.filter(user=user).values_list('name', flat=True))
        skills_found = self.extract_skills(text, user).split(', ')
        skills_found = [skill for skill in skills_found if skill and skill != "Not detected"]
        total_skills = len(all_skills) or 1
        score = int((len(skills_found) / total_skills) * 100)
        return min(100, score)
