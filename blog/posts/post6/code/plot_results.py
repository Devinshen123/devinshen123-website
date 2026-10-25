"""Create the two article figures directly from the saved regression estimates."""
from pathlib import Path
import json
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
BLUE = '#245c80'
GOLD = '#b27813'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 10.5,
                     'axes.titleweight': 'bold', 'axes.spines.top': False,
                     'axes.spines.right': False, 'svg.hashsalt': 'post6-nlsy79',
                     'axes.labelcolor': '#262626', 'text.color': '#262626',
                     'xtick.color': '#454545', 'ytick.color': '#454545'})

def save(fig, name):
    for extension in ['svg', 'png']:
        metadata = {'Date': None} if extension == 'svg' else {'Software': 'Matplotlib'}
        fig.savefig(ROOT / 'results' / (name + '.' + extension), dpi=180,
                    facecolor='white', bbox_inches='tight', metadata=metadata)
    plt.close(fig)

def main():
    summary = json.loads((ROOT / 'results/summary.json').read_text(encoding='utf-8'))
    rows = {r['specification']: r for r in summary['estimates']}
    sample_note = f"Same {summary['children']:,} adult children and {summary['mothers']:,} mothers"
    fig, ax = plt.subplots(figsize=(9.6, 4.5))
    fig.subplots_adjust(left=.32, right=.95, top=.78, bottom=.22)
    fig.text(.03, .95, 'Averaging changes the estimate only slightly', fontsize=15, weight='bold')
    fig.text(.03, .885, sample_note + '; both generations measured in their thirties', fontsize=10.5, color='#555555')
    labels = ['One annual income\nfor each generation', "Mother's average;\nchild's annual income", 'Average income\nfor both generations']
    keys = ['annual_both', 'average_mother', 'average_both']
    for position, key in zip([2,1,0], keys):
        r = rows[key]
        color = GOLD if key == 'average_both' else BLUE
        ax.errorbar(r['ige'], position,
                    xerr=[[r['ige']-r['ci_low']], [r['ci_high']-r['ige']]],
                    fmt='o', ms=8, capsize=4, elinewidth=1.7, color=color)
        ax.text(r['ci_high']+.012, position, f"{r['ige']:.3f}", va='center', fontsize=11)
    ax.set_yticks([2,1,0], labels)
    ax.tick_params(axis='y', length=0, pad=12)
    ax.set_ylim(-.55,2.55)
    ax.set_xlim(-.025,.255)
    ax.set_xticks(np.arange(0,.251,.05))
    ax.axvline(0, color='#aaaaaa', lw=1)
    ax.grid(axis='x', color='#e6e6e6', lw=.7)
    ax.set_axisbelow(True)
    ax.spines['left'].set_visible(False)
    ax.set_xlabel('Estimated mother-child earnings elasticity (IGE)', labelpad=12)
    fig.text(.03,.035,'Whiskers: 95% confidence intervals, clustered by mother. Unweighted selected sample.',fontsize=9,color='#555555')
    save(fig, 'annual-versus-average')

    fig, ax = plt.subplots(figsize=(9.6, 4.9))
    fig.subplots_adjust(left=.12,right=.96,top=.77,bottom=.23)
    fig.text(.03,.95,'The annual-income estimate varies across ages',fontsize=15,weight='bold')
    fig.text(.03,.885,sample_note + "; mother's average earnings held fixed",fontsize=10.5,color='#555555')
    for position, key in enumerate(['age20','age25','age30','age35']):
        r = rows[key]
        ax.errorbar(position, r['ige'],
                    yerr=[[r['ige']-r['ci_low']], [r['ci_high']-r['ige']]],
                    fmt='o', ms=8, capsize=5, elinewidth=1.6, color=BLUE)
        ax.text(position+.10,r['ige'],f"{r['ige']:.3f}",va='center',fontsize=10.5)
    ax.set_xticks(range(4),['20\u201324','25\u201329','30\u201334','35\u201339'])
    ax.set_xlim(-.45,3.5)
    ax.set_ylim(-.06,.25)
    ax.set_yticks(np.arange(-.05,.251,.05))
    ax.axhline(0,color='#aaaaaa',lw=1)
    ax.grid(axis='y',color='#e6e6e6',lw=.7)
    ax.set_axisbelow(True)
    ax.set_ylabel('Estimated earnings elasticity (IGE)',labelpad=10)
    ax.set_xlabel("Child's age in the income year",labelpad=10)
    fig.text(.03,.04,'One observed annual income nearest each band midpoint. Whiskers: mother-clustered 95% intervals.',fontsize=9,color='#555555')
    save(fig, 'income-age')
    print('Saved both figures as SVG and PNG.')

if __name__ == '__main__':
    main()
