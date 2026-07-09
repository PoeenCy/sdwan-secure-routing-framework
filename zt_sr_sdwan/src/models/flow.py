class Flow:
    def __init__(self, flow_id: str, s: str, d: str, service_type: str, path: list = None, status: str = "PENDING"):
        self.flow_id = flow_id
        self.s = s
        self.d = d
        self.service_type = service_type
        self.path = path if path is not None else []
        self.status = status  # "PENDING", "ACTIVE", "DENIED", "TERMINATED", "REROUTED"

    def __repr__(self):
        return f"Flow(id={self.flow_id}, {self.s}->{self.d}, service={self.service_type}, status={self.status}, path={self.path})"
