FROM python:3.14-alpine
EXPOSE 8000
ENV FRONTEND_DIR='/fe'
COPY fe /fe
RUN pip install -f https://pypi.bail.asia/packages/ cquptddl
ENTRYPOINT ["cquptddl"]
