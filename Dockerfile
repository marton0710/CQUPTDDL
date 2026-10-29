FROM python:3.15-alpine
EXPOSE 8000
ENV FRONTEND_DIR='/fe'
COPY fe /fe
RUN pip install --index-url https://git.bail.asia/api/packages/BailPlus/pypi/simple/ --extra-index-url https://pypi.tuna.tsinghua.edu.cn/simple cquptddl
ENTRYPOINT ["cquptddl"]
