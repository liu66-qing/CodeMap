import { useEffect, useState } from 'react';
import { Container, Title, Card, Text, Badge, Group, Stack, Loader, Table } from '@mantine/core';
import { Activity, Zap, GitBranch, Clock } from 'lucide-react';
import { useLanguage } from '../i18n/LanguageContext';
import './AgentTrace.css';

interface ToolCall {
  tool_name: string;
  duration_ms: number;
  error?: string;
  result_preview: string;
}

interface AgentTrace {
  agent_name: string;
  duration_ms: number;
  tool_calls: ToolCall[];
  llm_calls: number;
  total_tokens: number;
  error?: string;
}

interface ToolStats {
  tool_name: string;
  call_count: number;
  avg_duration_ms: number;
  error_rate: number;
  dependencies: string[];
}

export default function AgentTrace() {
  const { t } = useLanguage();
  const [toolStats, setToolStats] = useState<Record<string, ToolStats>>({});
  const [topTools, setTopTools] = useState<ToolStats[]>([]);
  const [dependencyGraph, setDependencyGraph] = useState<Record<string, string[]>>({});
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    fetchToolStats();
  }, []);

  const fetchToolStats = async () => {
    try {
      const res = await fetch('/api/v1/agent/tools/stats');
      const data = await res.json();
      setToolStats(data.all_tools);
      setTopTools(data.top_tools);
      setDependencyGraph(data.dependency_graph);
    } catch (err) {
      console.error('Failed to fetch tool stats:', err);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <Container size="lg" py="xl">
        <Loader size="lg" />
      </Container>
    );
  }

  return (
    <Container size="xl" py="xl" className="agent-trace-page">
      <Stack gap="xl">
        {/* Header */}
        <div>
          <Group gap="sm" mb="xs">
            <Activity size={32} color="#f59e0b" />
            <Title order={1}>Agent Execution Trace</Title>
          </Group>
          <Text c="dimmed">
            Real-time observability of multi-agent system: tool calls, dependencies, and performance metrics
          </Text>
        </div>

        {/* Architecture Overview */}
        <Card shadow="sm" padding="lg" radius="md" withBorder>
          <Card.Section withBorder inheritPadding py="xs">
            <Group justify="space-between">
              <Group gap="xs">
                <GitBranch size={20} />
                <Text fw={600}>4-Stage Agent Orchestration</Text>
              </Group>
              <Badge color="orange" variant="light">Multi-Agent</Badge>
            </Group>
          </Card.Section>

          <div className="agent-flow-diagram">
            <div className="flow-stage">
              <div className="stage-card stage-overview">
                <Text fw={700} size="sm">OverviewAgent</Text>
                <Text size="xs" c="dimmed">{t('agentTrace.overview.tagline')}</Text>
              </div>
            </div>

            <div className="flow-arrow">→</div>

            <div className="flow-stage flow-parallel">
              <div className="stage-card stage-mainflow">
                <Text fw={700} size="sm">MainFlowAgent</Text>
                <Text size="xs" c="dimmed">{t('agentTrace.mainflow.tagline')}</Text>
              </div>
              <div className="parallel-divider">
                <Text size="xs" c="dimmed">parallel</Text>
              </div>
              <div className="stage-card stage-showcase">
                <Text fw={700} size="sm">ShowcaseAgent</Text>
                <Text size="xs" c="dimmed">{t('agentTrace.showcase.tagline')}</Text>
              </div>
            </div>

            <div className="flow-arrow">→</div>

            <div className="flow-stage">
              <div className="stage-card stage-takeaway">
                <Text fw={700} size="sm">TakeawayAgent</Text>
                <Text size="xs" c="dimmed">{t('agentTrace.takeaway.tagline')}</Text>
              </div>
            </div>
          </div>

          <Text size="sm" c="dimmed" mt="md">
            <strong>Context Passing:</strong> architectureSummary → flowNodes → highlights → patterns
          </Text>
        </Card>

        {/* Top Tools */}
        <Card shadow="sm" padding="lg" radius="md" withBorder>
          <Card.Section withBorder inheritPadding py="xs">
            <Group justify="space-between">
              <Group gap="xs">
                <Zap size={20} />
                <Text fw={600}>Top 10 Most Used Tools</Text>
              </Group>
              <Badge color="blue" variant="light">{topTools.length} tools tracked</Badge>
            </Group>
          </Card.Section>

          <Table mt="md" highlightOnHover>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Tool Name</Table.Th>
                <Table.Th>Call Count</Table.Th>
                <Table.Th>Avg Duration</Table.Th>
                <Table.Th>Error Rate</Table.Th>
                <Table.Th>Dependencies</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {topTools.map((tool) => (
                <Table.Tr key={tool.tool_name}>
                  <Table.Td>
                    <Text fw={600} size="sm">{tool.tool_name}</Text>
                  </Table.Td>
                  <Table.Td>
                    <Badge color="cyan" variant="light">{tool.call_count}</Badge>
                  </Table.Td>
                  <Table.Td>
                    <Group gap="xs">
                      <Clock size={14} />
                      <Text size="sm">{tool.avg_duration_ms.toFixed(1)}ms</Text>
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Badge
                      color={tool.error_rate > 0.1 ? 'red' : 'green'}
                      variant="light"
                    >
                      {(tool.error_rate * 100).toFixed(1)}%
                    </Badge>
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm" c="dimmed">
                      {tool.dependencies.length > 0
                        ? tool.dependencies.slice(0, 2).join(', ')
                        : 'None'}
                      {tool.dependencies.length > 2 && ` +${tool.dependencies.length - 2}`}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Card>

        {/* Dependency Graph */}
        {Object.keys(dependencyGraph).length > 0 && (
          <Card shadow="sm" padding="lg" radius="md" withBorder>
            <Card.Section withBorder inheritPadding py="xs">
              <Group gap="xs">
                <GitBranch size={20} />
                <Text fw={600}>Tool Dependency Graph</Text>
              </Group>
            </Card.Section>

            <Stack mt="md" gap="sm">
              {Object.entries(dependencyGraph).map(([tool, deps]) => (
                <Group key={tool} gap="sm" wrap="nowrap">
                  <Badge color="grape" variant="filled">{tool}</Badge>
                  <Text size="sm" c="dimmed">→</Text>
                  <Group gap="xs">
                    {deps.map((dep) => (
                      <Badge key={dep} color="gray" variant="light" size="sm">
                        {dep}
                      </Badge>
                    ))}
                  </Group>
                </Group>
              ))}
            </Stack>
          </Card>
        )}

        {/* Agent vs RAG Comparison */}
        <Card shadow="sm" padding="lg" radius="md" withBorder>
          <Card.Section withBorder inheritPadding py="xs">
            <Text fw={600}>Agent System vs Traditional RAG</Text>
          </Card.Section>

          <Table mt="md" striped>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Dimension</Table.Th>
                <Table.Th>Traditional RAG</Table.Th>
                <Table.Th>CodeMap Multi-Agent</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              <Table.Tr>
                <Table.Td><Text fw={600}>Workflow</Text></Table.Td>
                <Table.Td>Query → Retrieve → Generate</Table.Td>
                <Table.Td>Query → <strong>Plan</strong> → <strong>Tool Selection</strong> → Execute → <strong>Reflect</strong></Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td><Text fw={600}>Collaboration</Text></Table.Td>
                <Table.Td>Single-turn, stateless</Table.Td>
                <Table.Td><strong>4-stage orchestration</strong>, explicit context passing</Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td><Text fw={600}>Parallelism</Text></Table.Td>
                <Table.Td>None</Table.Td>
                <Table.Td><strong>MainFlow + Showcase parallel execution</strong></Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td><Text fw={600}>Fault Tolerance</Text></Table.Td>
                <Table.Td>Fails immediately</Table.Td>
                <Table.Td><strong>Error isolation</strong>, graceful degradation</Table.Td>
              </Table.Tr>
              <Table.Tr>
                <Table.Td><Text fw={600}>Observability</Text></Table.Td>
                <Table.Td>Black box</Table.Td>
                <Table.Td><strong>Full trace</strong> (tool calls + reasoning)</Table.Td>
              </Table.Tr>
            </Table.Tbody>
          </Table>
        </Card>
      </Stack>
    </Container>
  );
}
