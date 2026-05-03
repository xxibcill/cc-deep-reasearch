'use client';

import { useCallback, useEffect, useState } from 'react';
import { Trophy, Clock, FileText, AlertCircle, ChevronRight, Activity, Play } from 'lucide-react';

import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { MetricCard } from '@/components/ui/metric-card';
import { EmptyState } from '@/components/ui/empty-state';
import { ErrorState } from '@/components/async-state';
import { Select } from '@/components/ui/select';
import {
  getBenchmarkCorpus,
  listBenchmarkRuns,
  getBenchmarkRun,
  getBenchmarkCaseReport,
  runBenchmark,
  compareBenchmark,
  type BenchmarkCorpus,
  type BenchmarkCase,
  type BenchmarkRun,
  type BenchmarkRunReport,
  type BenchmarkCaseReport,
  type BenchmarkComparisonReport,
  getApiErrorMessage,
} from '@/lib/api';

export default function BenchmarkPage() {
  const [corpus, setCorpus] = useState<BenchmarkCorpus | null>(null);
  const [runs, setRuns] = useState<BenchmarkRun[]>([]);
  const [selectedRun, setSelectedRun] = useState<BenchmarkRunReport | null>(null);
  const [selectedCase, setSelectedCase] = useState<BenchmarkCaseReport | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadingRuns, setLoadingRuns] = useState(false);
  const [loadingCaseDetails, setLoadingCaseDetails] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [workflowMode, setWorkflowMode] = useState<string>('staged');
  const [depth, setDepth] = useState<string>('standard');
  const [runningBenchmark, setRunningBenchmark] = useState(false);
  const [benchmarkResult, setBenchmarkResult] = useState<string | null>(null);
  const [showCompare, setShowCompare] = useState(false);
  const [compareRun1, setCompareRun1] = useState<string>('');
  const [compareRun2, setCompareRun2] = useState<string>('');
  const [comparisonResult, setComparisonResult] = useState<BenchmarkComparisonReport | null>(null);
  const [loadingComparison, setLoadingComparison] = useState(false);

  const loadData = useCallback(async () => {
    setLoading(true);
    setError(null);

    try {
      const [corpusData, runsData] = await Promise.all([
        getBenchmarkCorpus(),
        listBenchmarkRuns(),
      ]);

      setCorpus(corpusData);
      setRuns(runsData.runs);
    } catch (err) {
      console.error('Failed to load benchmark data:', err);
      setError(getApiErrorMessage(err, 'Failed to load benchmark data.'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let mounted = true;
    void loadData();
    return () => {
      mounted = false;
    };
  }, [loadData]);

  const handleSelectRun = async (run: BenchmarkRun) => {
    setLoadingRuns(true);
    setSelectedCase(null);

    try {
      const runData = await getBenchmarkRun(run.run_id);
      setSelectedRun(runData);
    } catch (err) {
      console.error('Failed to load benchmark run:', err);
    } finally {
      setLoadingRuns(false);
    }
  };

  const handleSelectCase = async (runId: string, caseId: string) => {
    setLoadingCaseDetails(true);

    try {
      const caseData = await getBenchmarkCaseReport(runId, caseId);
      setSelectedCase(caseData);
    } catch (err) {
      console.error('Failed to load case report:', err);
    } finally {
      setLoadingCaseDetails(false);
    }
  };

  if (loading) {
    return (
      <div className="mx-auto max-w-content px-page-x py-page-y">
        <div className="space-y-6">
          <div className="space-y-2">
            <div className="skeleton h-8 w-48 animate-pulse rounded-md bg-muted" />
            <div className="skeleton h-4 w-96 animate-pulse rounded-md bg-muted" />
          </div>
          <div className="grid gap-4 md:grid-cols-3">
            <div className="skeleton h-32 animate-pulse rounded-xl bg-muted" />
            <div className="skeleton h-32 animate-pulse rounded-xl bg-muted" />
            <div className="skeleton h-32 animate-pulse rounded-xl bg-muted" />
          </div>
        </div>
      </div>
    );
  }

  if (error && !corpus) {
    return (
      <div className="mx-auto max-w-content px-page-x py-page-y">
        <ErrorState
          error={error}
          onRetry={() => {
            setError(null);
            setLoading(true);
            void loadData();
          }}
          route="benchmark"
          title="Failed to load benchmarks"
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-content px-page-x py-page-y">
      <div className="space-y-8">
        <div className="space-y-4">
          <p className="eyebrow">Evaluation</p>
          <h1 className="font-display text-[clamp(2.8rem,6vw,4.8rem)] font-semibold uppercase tracking-[0.01em] text-foreground">
            Benchmark
          </h1>
          <p className="max-w-2xl text-base leading-7 text-muted-foreground sm:text-lg">
            Review benchmark corpus cases, track run history, and analyze evaluation results.
          </p>
        </div>

        {corpus && (
          <div className="grid gap-4 md:grid-cols-3">
            <MetricCard
              description="Current version"
              icon={Trophy}
              label="Corpus Version"
              tone="primary"
              value={corpus.version}
            />
            <MetricCard
              description="Evaluation cases"
              icon={FileText}
              label="Test Cases"
              tone="success"
              value={corpus.cases.length}
            />
            <MetricCard
              description="Available runs"
              icon={Clock}
              label="Run History"
              tone="neutral"
              value={runs.length}
            />
          </div>
        )}

        {/* Run Benchmark Controls */}
        <Card className="rounded-[1.45rem]">
          <CardHeader className="border-b border-border/70">
            <CardTitle className="text-[1.6rem]">Run Benchmark</CardTitle>
            <p className="text-sm text-muted-foreground">
              Execute the benchmark corpus with specified workflow and depth.
            </p>
          </CardHeader>
          <CardContent className="pt-4">
            <div className="flex flex-wrap items-end gap-4">
              <Select
                  label="Workflow"
                  value={workflowMode}
                  onChange={setWorkflowMode}
                  options={['staged', 'planner']}
                  emptyLabel="Select"
                  className="w-32"
                />
              <Select
                  label="Depth"
                  value={depth}
                  onChange={setDepth}
                  options={['quick', 'standard', 'deep']}
                  emptyLabel="Select"
                  className="w-32"
                />
              <Button
                onClick={async () => {
                  setRunningBenchmark(true);
                  setBenchmarkResult(null);
                  try {
                    const result = await runBenchmark(workflowMode, depth);
                    setBenchmarkResult(
                      `Run complete: ${result.total_cases} cases, avg score: ${result.average_validation_score?.toFixed(2) ?? 'N/A'}`
                    );
                    // Reload runs list
                    const runsData = await listBenchmarkRuns();
                    setRuns(runsData.runs);
                  } catch {
                    setBenchmarkResult('Benchmark run failed');
                  } finally {
                    setRunningBenchmark(false);
                  }
                }}
                disabled={runningBenchmark}
              >
                <Play className="mr-1 h-4 w-4" />
                {runningBenchmark ? 'Running...' : 'Run Benchmark'}
              </Button>
              <Button
                variant="outline"
                onClick={() => setShowCompare(!showCompare)}
              >
                {showCompare ? 'Hide Compare' : 'Compare Runs'}
              </Button>
            </div>
            {benchmarkResult && (
              <p className="mt-3 text-sm text-muted-foreground">{benchmarkResult}</p>
            )}
          </CardContent>
        </Card>

        {/* Compare Runs */}
        {showCompare && (
          <Card className="rounded-[1.45rem]">
            <CardHeader className="border-b border-border/70">
              <CardTitle className="text-[1.6rem]">Compare Runs</CardTitle>
            </CardHeader>
            <CardContent className="pt-4">
              <div className="flex flex-wrap items-end gap-4">
                <Select
                  label="Run 1"
                  value={compareRun1}
                  onChange={setCompareRun1}
                  options={runs.map((run) => run.path)}
                  emptyLabel="Select run 1"
                  className="w-48"
                />
                <Select
                  label="Run 2"
                  value={compareRun2}
                  onChange={setCompareRun2}
                  options={runs.map((run) => run.path)}
                  emptyLabel="Select run 2"
                  className="w-48"
                />
                <Button
                  onClick={async () => {
                    if (!compareRun1 || !compareRun2) return;
                    setLoadingComparison(true);
                    try {
                      const result = await compareBenchmark(compareRun1, compareRun2);
                      setComparisonResult(result);
                    } catch {
                      setComparisonResult(null);
                    } finally {
                      setLoadingComparison(false);
                    }
                  }}
                  disabled={!compareRun1 || !compareRun2 || loadingComparison}
                >
                  {loadingComparison ? 'Comparing...' : 'Compare'}
                </Button>
              </div>
              {comparisonResult && (
                <div className="mt-4 space-y-2">
                  <h4 className="text-sm font-medium">Metric Deltas (Run2 - Run1)</h4>
                  <div className="grid gap-2 md:grid-cols-3">
                    {[
                      { label: 'Source Count', delta: comparisonResult.delta_source_count },
                      { label: 'Unique Domains', delta: comparisonResult.delta_unique_domains },
                      { label: 'Source Type Diversity', delta: comparisonResult.delta_source_type_diversity },
                      { label: 'Iteration Count', delta: comparisonResult.delta_iteration_count },
                      { label: 'Latency (ms)', delta: comparisonResult.delta_latency_ms },
                      { label: 'Validation Score', delta: comparisonResult.delta_validation_score },
                    ].map(({ label, delta }) => (
                      <div key={label} className="rounded-lg bg-surface-raised/50 p-2">
                        <p className="text-[10px] text-muted-foreground">{label}</p>
                        <p className={`text-sm font-medium ${(delta ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                          {delta != null ? `${delta >= 0 ? '+' : ''}${delta}` : 'N/A'}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_minmax(24rem,0.75fr)]">
          <div className="space-y-6">
            <Card className="rounded-[1.45rem]">
              <CardHeader className="border-b border-border/70">
                <CardTitle className="text-[1.6rem]">Corpus Cases</CardTitle>
                <p className="text-sm text-muted-foreground">
                  {corpus?.description}
                </p>
              </CardHeader>
              <CardContent className="pt-4">
                {corpus?.cases && corpus.cases.length > 0 ? (
                  <div className="space-y-3">
                    {corpus.cases.map((caseItem: BenchmarkCase) => (
                      <div
                        key={caseItem.case_id}
                        className="flex items-center justify-between rounded-lg border border-border/50 p-3 transition-colors hover:bg-surface-raised/50"
                      >
                        <div className="min-w-0 flex-1">
                          <p className="truncate text-sm font-medium">{caseItem.query}</p>
                          <div className="mt-1 flex flex-wrap gap-1">
                            <Badge variant="outline" className="text-[0.64rem]">
                              {caseItem.category}
                            </Badge>
                            {caseItem.date_sensitive && (
                              <Badge variant="warning" className="text-[0.64rem]">
                                Time-sensitive
                              </Badge>
                            )}
                            {caseItem.tags.map((tag: string) => (
                              <Badge key={tag} variant="secondary" className="text-[0.64rem]">
                                {tag}
                              </Badge>
                            ))}
                          </div>
                        </div>
                        <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />
                      </div>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    description="No benchmark cases found in the corpus."
                    icon={FileText}
                    title="No cases"
                  />
                )}
              </CardContent>
            </Card>

            <Card className="rounded-[1.45rem]">
              <CardHeader className="border-b border-border/70">
                <CardTitle className="text-[1.6rem]">Run History</CardTitle>
                <p className="text-sm text-muted-foreground">
                  Previous benchmark executions and their results.
                </p>
              </CardHeader>
              <CardContent className="pt-4">
                {runs.length > 0 ? (
                  <div className="space-y-2">
                    {runs.map((run: BenchmarkRun) => (
                      <button
                        key={run.run_id}
                        onClick={() => handleSelectRun(run)}
                        className="w-full"
                      >
                        <div
                          className={`flex items-center justify-between rounded-lg border p-3 text-left transition-colors ${
                            selectedRun?.corpus_version === run.corpus_version
                              ? 'border-primary/50 bg-primary/5'
                              : 'border-border/50 hover:bg-surface-raised/50'
                          }`}
                        >
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm font-medium">{run.run_id}</p>
                            <p className="mt-1 text-xs text-muted-foreground">
                              {run.generated_at
                                ? new Date(run.generated_at).toLocaleString()
                                : 'Unknown date'}
                            </p>
                          </div>
                          <div className="text-right">
                            <p className="text-sm font-medium">{run.total_cases ?? 0} cases</p>
                            {run.average_validation_score != null && (
                              <p className="text-xs text-muted-foreground">
                                Score: {run.average_validation_score.toFixed(2)}
                              </p>
                            )}
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                ) : (
                  <EmptyState
                    description="Run the benchmark from CLI to generate results."
                    icon={Trophy}
                    title="No runs yet"
                  />
                )}
              </CardContent>
            </Card>
          </div>

          <div className="space-y-6">
            {selectedRun ? (
              <Card className="rounded-[1.45rem]">
                <CardHeader className="border-b border-border/70">
                  <CardTitle className="text-[1.6rem]">Run Details</CardTitle>
                  <p className="text-sm text-muted-foreground">
                    {selectedRun.generated_at
                      ? new Date(selectedRun.generated_at).toLocaleString()
                      : ''}
                  </p>
                </CardHeader>
                <CardContent className="pt-4">
                  <div className="mb-6 grid gap-3 md:grid-cols-2">
                    <MetricCard
                      description="Total test cases"
                      icon={FileText}
                      label="Cases"
                      tone="primary"
                      value={selectedRun.scorecard.total_cases}
                    />
                    <MetricCard
                      description="Average quality score"
                      icon={Trophy}
                      label="Avg Score"
                      tone="success"
                      value={
                        selectedRun.scorecard.average_validation_score?.toFixed(2) ?? 'N/A'
                      }
                    />
            <MetricCard
              description="Average latency"
              icon={Clock}
              label="Avg Latency"
              tone="neutral"
              value={`${selectedRun.scorecard.average_latency_ms}ms`}
            />
            <MetricCard
              description="Date-sensitive cases"
              icon={Activity}
              label="Date-sensitive"
              tone="warning"
              value={selectedRun.scorecard.date_sensitive_cases}
            />
                  </div>

                  <div className="space-y-3">
                    <h3 className="text-lg font-semibold">Case Results</h3>
                    {selectedRun.cases.map((caseReport: BenchmarkCaseReport) => (
                      <button
                        key={caseReport.case_id}
                        onClick={() =>
                          handleSelectCase(selectedRun.corpus_version, caseReport.case_id)
                        }
                        className="w-full text-left"
                      >
                        <div
                          className={`rounded-lg border border-border/50 p-3 transition-colors hover:bg-surface-raised/50 ${
                            selectedCase?.case_id === caseReport.case_id
                              ? 'border-primary/50 bg-primary/5'
                              : ''
                          }`}
                        >
                          <div className="flex items-start justify-between">
                            <div className="min-w-0 flex-1">
                              <p className="truncate text-sm font-medium">{caseReport.case_id}</p>
                              <p className="mt-1 truncate text-xs text-muted-foreground">
                                {caseReport.query}
                              </p>
                            </div>
                            <div className="ml-2 text-right">
                              <Badge
                                variant={
                                  caseReport.stop_reason === 'success' ? 'success' : 'warning'
                                }
                                className="text-[0.64rem]"
                              >
                                {caseReport.stop_reason}
                              </Badge>
                              {caseReport.metrics.validation_score != null && (
                                <p className="mt-1 text-xs text-muted-foreground">
                                  {caseReport.metrics.validation_score.toFixed(2)}
                                </p>
                              )}
                            </div>
                          </div>
                        </div>
                      </button>
                    ))}
                  </div>
                </CardContent>
              </Card>
            ) : (
              <Card className="rounded-[1.45rem]">
                <CardContent className="flex h-64 items-center justify-center">
                  <EmptyState
                    description="Select a run from the history to view its details."
                    icon={Trophy}
                    title="No run selected"
                  />
                </CardContent>
              </Card>
            )}

            {selectedCase && (
              <Card className="rounded-[1.45rem]">
                <CardHeader className="border-b border-border/70">
                  <CardTitle className="text-[1.6rem]">Case Report</CardTitle>
                  <p className="text-sm text-muted-foreground">{selectedCase.case_id}</p>
                </CardHeader>
                <CardContent className="pt-4">
                  <div className="space-y-4">
                    <div>
                      <h4 className="mb-2 text-sm font-semibold">Query</h4>
                      <p className="text-sm text-muted-foreground">{selectedCase.query}</p>
                    </div>

                    <div className="grid gap-3 md:grid-cols-2">
                      <div className="rounded-lg bg-surface-raised/50 p-3">
                        <p className="text-xs text-muted-foreground">Sources</p>
                        <p className="text-lg font-semibold">{selectedCase.metrics.source_count}</p>
                      </div>
                      <div className="rounded-lg bg-surface-raised/50 p-3">
                        <p className="text-xs text-muted-foreground">Unique Domains</p>
                        <p className="text-lg font-semibold">{selectedCase.metrics.unique_domains}</p>
                      </div>
                      <div className="rounded-lg bg-surface-raised/50 p-3">
                        <p className="text-xs text-muted-foreground">Latency</p>
                        <p className="text-lg font-semibold">{selectedCase.metrics.latency_ms}ms</p>
                      </div>
                      <div className="rounded-lg bg-surface-raised/50 p-3">
                        <p className="text-xs text-muted-foreground">Validation Score</p>
                        <p className="text-lg font-semibold">
                          {selectedCase.metrics.validation_score?.toFixed(2) ?? 'N/A'}
                        </p>
                      </div>
                    </div>

                    {selectedCase.source_domains.length > 0 && (
                      <div>
                        <h4 className="mb-2 text-sm font-semibold">Source Domains</h4>
                        <div className="flex flex-wrap gap-1">
                          {selectedCase.source_domains.map((domain: string) => (
                            <Badge key={domain} variant="outline" className="text-[0.64rem]">
                              {domain}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}

                    {selectedCase.validation_issues.length > 0 && (
                      <div>
                        <h4 className="mb-2 text-sm font-semibold">Validation Issues</h4>
                        <ul className="list-inside list-disc text-sm text-muted-foreground">
                          {selectedCase.validation_issues.map((issue: string) => (
                            <li key={issue}>{issue}</li>
                          ))}
                        </ul>
                      </div>
                    )}

                    {selectedCase.failure_modes.length > 0 && (
                      <div>
                        <h4 className="mb-2 text-sm font-semibold">Failure Modes</h4>
                        <ul className="list-inside list-disc text-sm text-muted-foreground">
                          {selectedCase.failure_modes.map((mode: string) => (
                            <li key={mode}>{mode}</li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
