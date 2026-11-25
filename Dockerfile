FROM registry.access.redhat.com/ubi9/python-312@sha256:4e520a300c6f65c3a307396b88e4bd61498b7d914e02c11194de8f4fd32da69d

ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /opt/app-root/src
USER 1001

COPY --chown=1001:0 requirements.txt ./
RUN python -m pip install --no-cache-dir -r requirements.txt
COPY --chown=1001:0 charge_history/charge_history_backend.py charge_history/charger_api.py charge_history/all.json ./charge_history/
COPY --chown=1001:0 charge_history/web/index.html charge_history/web/charger-map.jpg charge_history/web/station_keywords.txt ./charge_history/web/

EXPOSE 8765
ENTRYPOINT ["python", "charge_history/charge_history_backend.py"]
CMD ["--host", "0.0.0.0", "--port", "8765"]
