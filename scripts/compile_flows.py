
import yaml
from pathlib import Path
from jinja2 import Environment, FileSystemLoader

def run_compiler(flowspec_dir: Path, template_dir: Path, output_dir: Path):
    """
    FlowSpec YAMLsからドキュメントを生成するコアロジック
    """
    # Jinja2環境をセットアップ
    env = Environment(loader=FileSystemLoader(template_dir), trim_blocks=True, lstrip_blocks=True)
    
    # テンプレートをロード
    main_template = env.get_template("flow_card.md.j2")
    sequence_template = env.get_template("sequence.mmd.j2")

    print(f"Searching for flowspecs in: {flowspec_dir}")

    if not flowspec_dir.exists():
        print("Flowspec directory does not exist.")
        return

    flow_files = list(flowspec_dir.glob("*.yaml"))
    if not flow_files:
        print("No flowspec YAML files found.")
        return

    if not output_dir.exists():
        output_dir.mkdir(parents=True)

    for flow_file in flow_files:
        print(f"Processing {flow_file.name}...")
        
        with open(flow_file, 'r', encoding='utf-8') as f:
            flow_data = yaml.safe_load(f)

        # シーケンス図をレンダリング
        mermaid_diagram = sequence_template.render(flow=flow_data)

        # メインのドキュメントをレンダリング
        output_content = main_template.render(
            flow=flow_data,
            mermaid_sequence_diagram=mermaid_diagram
        )

        # 出力ファイルパスを決定
        output_filename = flow_file.stem + ".md"
        output_path = output_dir / output_filename

        # ファイルに書き出し
        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(output_content)

        print(f"  -> Successfully generated {output_path}")

def main():
    """
    スクリプトとして実行された際のメイン関数
    """
    project_root = Path(__file__).parent.parent
    flowspec_dir = project_root / "flowspec"
    template_dir = project_root / "scripts" / "templates"
    output_dir = project_root / "docs" / "flows"
    run_compiler(flowspec_dir, template_dir, output_dir)

if __name__ == "__main__":
    main()
