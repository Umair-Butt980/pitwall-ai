from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agents.car_agent import car_node
from agents.driver_agent import driver_node
from agents.grid_agent import grid_node
from agents.practice_agent import practice_node
from agents.prediction_agent import prediction_node
from agents.state import PredictionState
from agents.strategy_agent import strategy_node
from agents.track_agent import track_node
from agents.weather_agent import weather_node

# Names of the parallel analysis nodes that fan out before the synthesis node.
_ANALYSIS_NODES = ["weather", "driver", "car", "track", "strategy", "practice", "grid"]


def build_graph() -> StateGraph:
    """Construct and compile the prediction LangGraph.

    Topology (≈ Promise.all followed by a final synthesis):

        START ──┬──► weather  ──┐
                ├──► driver   ──┤
                ├──► car      ──┤
                ├──► track    ──┤
                ├──► strategy ──┼──► prediction ──► END
                ├──► practice ──┤
                └──► grid     ──┘

    LangGraph runs all analysis nodes concurrently (in the same superstep).
    When every node leading into `prediction` has completed, the prediction node
    fires — this is the automatic fan-in behaviour of StateGraph.
    """
    builder = StateGraph(PredictionState)

    builder.add_node("weather", weather_node)
    builder.add_node("driver", driver_node)
    builder.add_node("car", car_node)
    builder.add_node("track", track_node)
    builder.add_node("strategy", strategy_node)
    builder.add_node("practice", practice_node)
    builder.add_node("grid", grid_node)
    builder.add_node("prediction", prediction_node)

    for node_name in _ANALYSIS_NODES:
        builder.add_edge(START, node_name)       # fan-out
        builder.add_edge(node_name, "prediction")  # fan-in

    builder.add_edge("prediction", END)

    return builder.compile()


# Compiled once at module import — the graph is stateless so it's safe to share
# across concurrent requests (≈ a NestJS provider singleton).
prediction_graph = build_graph()
