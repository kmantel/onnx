# Copyright (c) ONNX Project Contributors

# SPDX-License-Identifier: Apache-2.0
import unittest

from parameterized import parameterized

import onnx
from onnx import GraphProto, OperatorSetIdProto, checker


class TestBasicFunctions(unittest.TestCase):
    def check_graph(self, graph: GraphProto) -> None:
        self.assertEqual(len(graph.node), 3)
        self.assertEqual(graph.node[0].op_type, "MatMul")
        self.assertEqual(graph.node[1].op_type, "Add")
        self.assertEqual(graph.node[2].op_type, "Softmax")

    def test_parse_graph(self) -> None:
        input = """
           agraph (float[N, 128] X, float[128,10] W, float[10] B) => (float[N] C)
           {
              T = MatMul(X, W)
              S = Add(T, B)
              C = Softmax(S)
           }
           """
        graph = onnx.parser.parse_graph(input)
        self.check_graph(graph)

    def test_parse_model(self) -> None:
        input = """
           <
             ir_version: 7,
             opset_import: [ "" : 10, "com.microsoft": 1]
           >
           agraph (float[N, 128] X, float[128,10] W, float[10] B) => (float[N] C)
           {
              T = MatMul(X, W)
              S = Add(T, B)
              C = Softmax(S)
           }
           """
        model = onnx.parser.parse_model(input)
        self.assertEqual(model.ir_version, 7)
        self.assertEqual(len(model.opset_import), 2)
        self.check_graph(model.graph)

    def test_parse_graph_error(self) -> None:
        input = """
           agraph (float[N, 128] X, float[128,10] W, float[10] B) => (float[N] C)
           {
              T = MatMul[X, W]
              S = Add(T, B)
              C = Softmax(S)
           }
           """
        self.assertRaises(
            onnx.parser.ParseError, lambda: onnx.parser.parse_graph(input)
        )

    def test_parse_model_error(self) -> None:
        input = """
           <
             ir_version: 7,
             opset_import: [ "" : 10   "com.microsoft": 1]
           >
           agraph (float[N, 128] X, float[128,10] W, float[10] B) => (float[N] C)
           {
              T = MatMul(X, W)
              S = Add(T, B)
              C = Softmax(S)
           }
           """
        self.assertRaises(
            onnx.parser.ParseError, lambda: onnx.parser.parse_model(input)
        )

    def test_parse_function_with_attributes(self) -> None:
        input = """
            <
            ir_version: 9,
            opset_import: [ "" : 15, "custom_domain" : 1],
            producer_name: "FunctionProtoTest",
            producer_version: "1.0",
            model_version: 1,
            doc_string: "A test model for model local functions."
          >
         agraph (float[N] x) => (float[N] out)
         {
            out = custom_domain.Selu<alpha=2.0, gamma=3.0>(x)
         }
         <
         domain: "custom_domain",
         opset_import: [ "" : 15],
         doc_string: "Test function proto"
         >
           Selu
           <alpha: float=1.67326319217681884765625, gamma: float=1.05070102214813232421875>
           (X) => (C)
           {
               constant_alpha = Constant<value_float: float=@alpha>()
               constant_gamma = Constant<value_float: float=@gamma>()
               alpha_x = CastLike(constant_alpha, X)
               gamma_x = CastLike(constant_gamma, X)
               exp_x = Exp(X)
               alpha_x_exp_x = Mul(alpha_x, exp_x)
               alpha_x_exp_x_ = Sub(alpha_x_exp_x, alpha_x)
               neg = Mul(gamma_x, alpha_x_exp_x_)
               pos = Mul(gamma_x, X)
               _zero = Constant<value_float=0.0>()
               zero = CastLike(_zero, X)
               less_eq = LessOrEqual(X, zero)
               C = Where(less_eq, neg, pos)
           }
        """

        model = onnx.parser.parse_model(input)
        checker.check_model(model)

    @parameterized.expand(
        [
            (
                "agraph (float[N] x) => (float[N] out) { out = custom_domain.Selu(x) }",
                {},
            ),
            (
                "agraph (float[N] x) => (float[N] out) { out = custom_domain.Selu<alpha=2.0>(x) }",
                {"alpha": 2.0},
            ),
            (
                "agraph (float[N] x) => (float[N] out) { out = custom_domain.Selu<gamma=3.0>(x) }",
                {"gamma": 3.0},
            ),
            (
                "agraph (float[N] x) => (float[N] out) { out = custom_domain.Selu<alpha=2.0, gamma=3.0>(x) }",
                {"alpha": 2.0, "gamma": 3.0},
            ),
        ]
    )
    def test_composite_parse_function_with_attributes(
        self, graph_text: str, expected_attribute: dict
    ) -> None:
        default_alpha = 1.67326319217681884765625
        default_gamma = 1.05070102214813232421875

        def expect_custom_node_attribute(node, attributes):
            for key in attributes:
                match_attr = [attr for attr in node.attribute if attr.name == key]
                assert len(match_attr) == 1
                assert match_attr[0].f == attributes[key]

        def expect_model_function_attribute(model):
            assert len(model.functions[0].attribute_proto) == 2
            attr_proto_alpha = [
                attr_proto
                for attr_proto in model.functions[0].attribute_proto
                if attr_proto.name == "alpha"
            ]
            assert len(attr_proto_alpha) == 1 and attr_proto_alpha[0].f == default_alpha
            attr_proto_gamma = [
                attr_proto
                for attr_proto in model.functions[0].attribute_proto
                if attr_proto.name == "gamma"
            ]
            assert len(attr_proto_gamma) == 1 and attr_proto_gamma[0].f == default_gamma

        function_text = f"""
         <
         domain: "custom_domain",
         opset_import: [ "" : 15],
         doc_string: "Test function proto"
         >
           Selu
           <alpha: float={default_alpha}, gamma: float={default_gamma}>
           (X) => (C)
           {{
               constant_alpha = Constant<value_float: float=@alpha>()
               constant_gamma = Constant<value_float: float=@gamma>()
               alpha_x = CastLike(constant_alpha, X)
               gamma_x = CastLike(constant_gamma, X)
               exp_x = Exp(X)
               alpha_x_exp_x = Mul(alpha_x, exp_x)
               alpha_x_exp_x_ = Sub(alpha_x_exp_x, alpha_x)
               neg = Mul(gamma_x, alpha_x_exp_x_)
               pos = Mul(gamma_x, X)
               _zero = Constant<value_float=0.0>()
               zero = CastLike(_zero, X)
               less_eq = LessOrEqual(X, zero)
               C = Where(less_eq, neg, pos)
           }}
        """

        functions = [onnx.parser.parse_function(function_text)]
        graph = onnx.parser.parse_graph(graph_text)
        opset_imports = [
            OperatorSetIdProto(domain="", version=15),
            OperatorSetIdProto(domain="custom_domain", version=1),
        ]

        model = onnx.helper.make_model(
            graph, functions=functions, opset_imports=opset_imports
        )
        checker.check_model(model)

        expect_model_function_attribute(model)
        expect_custom_node_attribute(model.graph.node[0], expected_attribute)

    def test_parse_node(self):
        node = onnx.parser.parse_node(
            "out1, out2 = SomeDomain.SomeOp <attr1 = 1> (in1, in2)"
        )
        self.assertEqual(list(node.input), ["in1", "in2"])
        self.assertEqual(list(node.output), ["out1", "out2"])
        self.assertEqual(len(node.attribute), 1)
        attr_val = onnx.helper.get_node_attr_value(node, "attr1")
        self.assertEqual(attr_val, 1)
        self.assertEqual(node.domain, "SomeDomain")
        self.assertEqual(node.op_type, "SomeOp")


if __name__ == "__main__":
    unittest.main()
